"""Unit tests for alerts API routes.

Tests the alert rules and alert instance management endpoints:
- GET /api/alerts/rules - List all rules with filtering and pagination
- POST /api/alerts/rules - Create new alert rule
- GET /api/alerts/rules/{rule_id} - Get specific rule
- PUT /api/alerts/rules/{rule_id} - Update rule
- DELETE /api/alerts/rules/{rule_id} - Delete rule
- POST /api/alerts/rules/{rule_id}/test - Test rule against events
- POST /api/alerts/{alert_id}/acknowledge - Acknowledge alert
- POST /api/alerts/{alert_id}/dismiss - Dismiss alert

These tests follow TDD methodology - comprehensive coverage of happy paths,
error cases, and edge cases with proper mocking.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.api.schemas.alerts import AlertSeverity
from backend.models.alert import Alert, AlertRule, AlertStatusEnum
from backend.models.alert import AlertSeverity as ModelAlertSeverity


def create_mock_rule(
    *,
    id: str = "rule-1",
    name: str = "Test Rule",
    description: str | None = None,
    enabled: bool = True,
    severity: ModelAlertSeverity = ModelAlertSeverity.HIGH,
    risk_threshold: int | None = 70,
    object_types: list[str] | None = None,
    camera_ids: list[str] | None = None,
    zone_ids: list[str] | None = None,
    min_confidence: float | None = None,
    schedule: dict | None = None,
    conditions: dict | None = None,
    dedup_key_template: str = "{camera_id}:{rule_id}",
    cooldown_seconds: int = 300,
    channels: list[str] | None = None,
    dwell_time_enabled: bool = False,
    dwell_threshold_seconds: int | None = None,
    exclude_household_members: bool = False,
    threat_detection_enabled: bool = False,
    threat_types: list[str] | None = None,
    threat_min_severity: str | None = None,
    threat_confidence_threshold: float | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> MagicMock:
    """Create a properly configured mock AlertRule with all required fields."""
    mock_rule = MagicMock(spec=AlertRule)
    mock_rule.id = id
    mock_rule.name = name
    mock_rule.description = description
    mock_rule.enabled = enabled
    mock_rule.severity = severity
    mock_rule.risk_threshold = risk_threshold
    mock_rule.object_types = object_types
    mock_rule.camera_ids = camera_ids
    mock_rule.zone_ids = zone_ids
    mock_rule.min_confidence = min_confidence
    mock_rule.schedule = schedule
    mock_rule.conditions = conditions
    mock_rule.dedup_key_template = dedup_key_template
    mock_rule.cooldown_seconds = cooldown_seconds
    mock_rule.channels = channels if channels is not None else []
    mock_rule.dwell_time_enabled = dwell_time_enabled
    mock_rule.dwell_threshold_seconds = dwell_threshold_seconds
    mock_rule.exclude_household_members = exclude_household_members
    mock_rule.threat_detection_enabled = threat_detection_enabled
    mock_rule.threat_types = threat_types
    mock_rule.threat_min_severity = threat_min_severity
    mock_rule.threat_confidence_threshold = threat_confidence_threshold
    mock_rule.created_at = (
        created_at if created_at is not None else datetime(2025, 1, 1, tzinfo=UTC)
    )
    mock_rule.updated_at = (
        updated_at if updated_at is not None else datetime(2025, 1, 1, tzinfo=UTC)
    )
    return mock_rule


class TestListRules:
    """Tests for GET /api/alerts/rules endpoint."""

    @pytest.mark.asyncio
    async def test_list_rules_no_filter(self) -> None:
        """Test listing all rules without filters."""
        from backend.api.routes.alerts import list_rules

        mock_db = AsyncMock()

        # Mock database query using helper
        mock_rule = create_mock_rule(
            id="rule-1",
            name="Test Rule",
            description="Test description",
            object_types=["person"],
            camera_ids=["cam1"],
            min_confidence=0.8,
            channels=["pushover"],
        )

        # Mock count query
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        # Mock rules query
        mock_rules_result = MagicMock()
        mock_rules_result.scalars.return_value.all.return_value = [mock_rule]

        mock_db.execute.side_effect = [mock_count_result, mock_rules_result]

        result = await list_rules(enabled=None, severity=None, limit=50, offset=0, db=mock_db)

        assert result.pagination.total == 1
        assert len(result.items) == 1
        assert result.items[0].id == "rule-1"
        assert result.items[0].name == "Test Rule"
        assert result.items[0].severity == AlertSeverity.HIGH

    @pytest.mark.asyncio
    async def test_list_rules_filter_by_enabled(self) -> None:
        """Test listing rules filtered by enabled status."""
        from backend.api.routes.alerts import list_rules

        mock_db = AsyncMock()

        # Mock count query
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        # Mock rules query using helper
        mock_rule = create_mock_rule(
            id="rule-enabled",
            name="Enabled Rule",
            enabled=True,
            severity=ModelAlertSeverity.MEDIUM,
            risk_threshold=50,
        )
        mock_rule.updated_at = datetime(2025, 1, 1, tzinfo=UTC)

        mock_rules_result = MagicMock()
        mock_rules_result.scalars.return_value.all.return_value = [mock_rule]

        mock_db.execute.side_effect = [mock_count_result, mock_rules_result]

        result = await list_rules(enabled=True, severity=None, limit=50, offset=0, db=mock_db)

        assert result.pagination.total == 1
        assert result.items[0].enabled is True

    @pytest.mark.asyncio
    async def test_list_rules_filter_by_severity(self) -> None:
        """Test listing rules filtered by severity."""
        from backend.api.routes.alerts import list_rules

        mock_db = AsyncMock()

        # Mock count query
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        # Mock rules query using helper
        mock_rule = create_mock_rule(
            id="rule-critical",
            name="Critical Rule",
            severity=ModelAlertSeverity.CRITICAL,
            risk_threshold=90,
            object_types=["person"],
        )

        mock_rules_result = MagicMock()
        mock_rules_result.scalars.return_value.all.return_value = [mock_rule]

        mock_db.execute.side_effect = [mock_count_result, mock_rules_result]

        result = await list_rules(enabled=None, severity="critical", limit=50, offset=0, db=mock_db)

        assert result.pagination.total == 1
        assert result.items[0].severity == AlertSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_list_rules_pagination(self) -> None:
        """Test listing rules with pagination."""
        from backend.api.routes.alerts import list_rules

        mock_db = AsyncMock()

        # Mock count query - total of 100 rules
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 100

        # Mock rules query - return 10 rules using helper
        mock_rules = [
            create_mock_rule(
                id=f"rule-{i}",
                name=f"Rule {i}",
                severity=ModelAlertSeverity.MEDIUM,
                risk_threshold=50,
            )
            for i in range(10)
        ]

        mock_rules_result = MagicMock()
        mock_rules_result.scalars.return_value.all.return_value = mock_rules

        mock_db.execute.side_effect = [mock_count_result, mock_rules_result]

        result = await list_rules(enabled=None, severity=None, limit=10, offset=0, db=mock_db)

        assert result.pagination.total == 100
        assert len(result.items) == 10
        assert result.pagination.has_more is True
        assert result.pagination.limit == 10
        assert result.pagination.offset == 0

    @pytest.mark.asyncio
    async def test_list_rules_empty(self) -> None:
        """Test listing rules when no rules exist."""
        from backend.api.routes.alerts import list_rules

        mock_db = AsyncMock()

        # Mock count query
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        # Mock empty rules query
        mock_rules_result = MagicMock()
        mock_rules_result.scalars.return_value.all.return_value = []

        mock_db.execute.side_effect = [mock_count_result, mock_rules_result]

        result = await list_rules(enabled=None, severity=None, limit=50, offset=0, db=mock_db)

        assert result.pagination.total == 0
        assert result.items == []
        assert result.pagination.has_more is False

    @pytest.mark.asyncio
    async def test_list_rules_sort_by_name(self) -> None:
        """Test listing rules are sorted by name."""
        from backend.api.routes.alerts import list_rules

        mock_db = AsyncMock()

        # Mock count query
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 2

        # Mock rules query - should be sorted alphabetically using helper
        mock_rule_a = create_mock_rule(
            id="rule-a",
            name="A Rule",
            severity=ModelAlertSeverity.MEDIUM,
            risk_threshold=50,
        )

        mock_rule_b = create_mock_rule(
            id="rule-b",
            name="B Rule",
            severity=ModelAlertSeverity.HIGH,
            risk_threshold=70,
            created_at=datetime(2025, 1, 2, tzinfo=UTC),
            updated_at=datetime(2025, 1, 2, tzinfo=UTC),
        )

        mock_rules_result = MagicMock()
        mock_rules_result.scalars.return_value.all.return_value = [
            mock_rule_a,
            mock_rule_b,
        ]

        mock_db.execute.side_effect = [mock_count_result, mock_rules_result]

        result = await list_rules(enabled=None, severity=None, limit=50, offset=0, db=mock_db)

        assert len(result.items) == 2
        assert result.items[0].name == "A Rule"
        assert result.items[1].name == "B Rule"


class TestCreateRule:
    """Tests for POST /api/alerts/rules endpoint."""

    @pytest.mark.asyncio
    async def test_create_rule_minimal(self) -> None:
        """Test creating a rule with minimal required fields."""
        from backend.api.routes.alerts import create_rule
        from backend.api.schemas.alerts import AlertRuleCreate, AlertSeverity

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_background_tasks = MagicMock()

        rule_data = AlertRuleCreate(
            name="Test Rule",
            severity=AlertSeverity.MEDIUM,
        )

        # Mock the created rule using helper
        with patch("backend.api.routes.alerts.AlertRule", autospec=True) as mock_rule_class:
            mock_rule_instance = create_mock_rule(
                id="new-rule-id",
                name="Test Rule",
                severity=ModelAlertSeverity.MEDIUM,
                risk_threshold=None,
            )

            mock_rule_class.return_value = mock_rule_instance

            result = await create_rule(
                rule_data, background_tasks=mock_background_tasks, db=mock_db, cache=mock_cache
            )

            assert result.id == "new-rule-id"
            assert result.name == "Test Rule"
            assert result.severity == AlertSeverity.MEDIUM
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            # NEM-3744: Cache invalidation is now deferred to background task
            mock_background_tasks.add_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_rule_with_schedule(self) -> None:
        """Test creating a rule with schedule conditions."""
        from backend.api.routes.alerts import create_rule
        from backend.api.schemas.alerts import (
            AlertRuleCreate,
            AlertRuleSchedule,
            AlertSeverity,
        )

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_background_tasks = MagicMock()

        schedule = AlertRuleSchedule(
            days=["monday", "tuesday"],
            start_time="22:00",
            end_time="06:00",
            timezone="America/New_York",
        )

        rule_data = AlertRuleCreate(
            name="Night Alert",
            severity=AlertSeverity.HIGH,
            risk_threshold=70,
            schedule=schedule,
        )

        # Mock the created rule using helper
        with patch("backend.api.routes.alerts.AlertRule", autospec=True) as mock_rule_class:
            mock_rule_instance = create_mock_rule(
                id="night-rule-id",
                name="Night Alert",
                severity=ModelAlertSeverity.HIGH,
                risk_threshold=70,
                schedule={
                    "days": ["monday", "tuesday"],
                    "start_time": "22:00",
                    "end_time": "06:00",
                    "timezone": "America/New_York",
                },
            )

            mock_rule_class.return_value = mock_rule_instance

            result = await create_rule(
                rule_data, background_tasks=mock_background_tasks, db=mock_db, cache=mock_cache
            )

            assert result.name == "Night Alert"
            assert result.schedule is not None
            mock_background_tasks.add_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_rule_severity_enum_conversion(self) -> None:
        """Test that severity is correctly converted from schema enum to model enum."""
        from backend.api.routes.alerts import create_rule
        from backend.api.schemas.alerts import AlertRuleCreate, AlertSeverity

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_background_tasks = MagicMock()

        rule_data = AlertRuleCreate(name="Critical Rule", severity=AlertSeverity.CRITICAL)

        with patch("backend.api.routes.alerts.AlertRule", autospec=True) as mock_rule_class:
            mock_rule_instance = create_mock_rule(
                id="critical-rule",
                name="Critical Rule",
                severity=ModelAlertSeverity.CRITICAL,
                risk_threshold=None,
            )

            mock_rule_class.return_value = mock_rule_instance

            result = await create_rule(
                rule_data, background_tasks=mock_background_tasks, db=mock_db, cache=mock_cache
            )

            assert result.severity == AlertSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_create_rule_cache_invalidation_failure(self) -> None:
        """Test creating rule schedules background task even if cache would fail."""
        from backend.api.routes.alerts import create_rule
        from backend.api.schemas.alerts import AlertRuleCreate, AlertSeverity

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_background_tasks = MagicMock()

        rule_data = AlertRuleCreate(name="Test Rule", severity=AlertSeverity.LOW)

        with patch("backend.api.routes.alerts.AlertRule", autospec=True) as mock_rule_class:
            mock_rule_instance = create_mock_rule(
                id="rule-id",
                name="Test Rule",
                severity=ModelAlertSeverity.LOW,
                risk_threshold=None,
            )

            mock_rule_class.return_value = mock_rule_instance

            # Background task is scheduled (actual cache invalidation happens later)
            result = await create_rule(
                rule_data, background_tasks=mock_background_tasks, db=mock_db, cache=mock_cache
            )

            assert result.id == "rule-id"
            mock_db.commit.assert_called_once()
            mock_background_tasks.add_task.assert_called_once()


class TestGetRule:
    """Tests for GET /api/alerts/rules/{rule_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_rule_success(self) -> None:
        """Test getting a rule by ID."""
        from backend.api.routes.alerts import get_rule

        mock_db = AsyncMock()

        mock_rule = create_mock_rule(
            id="test-rule-id",
            name="Test Rule",
            description="Test description",
            object_types=["person"],
            camera_ids=["cam1"],
            min_confidence=0.8,
            channels=["pushover"],
        )

        with patch(
            "backend.api.routes.alerts.get_alert_rule_or_404", return_value=mock_rule, autospec=True
        ):
            result = await get_rule(rule_id="test-rule-id", db=mock_db)

            assert result.id == "test-rule-id"
            assert result.name == "Test Rule"
            assert result.risk_threshold == 70

    @pytest.mark.asyncio
    async def test_get_rule_not_found(self) -> None:
        """Test getting non-existent rule raises 404."""
        from backend.api.routes.alerts import get_rule

        mock_db = AsyncMock()

        with patch(
            "backend.api.routes.alerts.get_alert_rule_or_404",
            side_effect=HTTPException(status_code=404, detail="Rule not found"),
            autospec=True,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_rule(rule_id="nonexistent", db=mock_db)

            assert exc_info.value.status_code == 404


class TestUpdateRule:
    """Tests for PUT /api/alerts/rules/{rule_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_rule_partial(self) -> None:
        """Test updating rule with partial data (exclude_unset=True)."""
        from backend.api.routes.alerts import update_rule
        from backend.api.schemas.alerts import AlertRuleUpdate

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_background_tasks = MagicMock()

        # Mock existing rule using helper
        mock_rule = create_mock_rule(
            id="rule-id",
            name="Original Name",
            description="Original description",
            severity=ModelAlertSeverity.MEDIUM,
            risk_threshold=50,
        )

        rule_update = AlertRuleUpdate(enabled=False)

        with patch(
            "backend.api.routes.alerts.get_alert_rule_or_404", return_value=mock_rule, autospec=True
        ):
            result = await update_rule(
                rule_id="rule-id",
                rule_data=rule_update,
                background_tasks=mock_background_tasks,
                db=mock_db,
                cache=mock_cache,
            )

            # Only enabled should be updated
            assert mock_rule.enabled is False
            mock_db.commit.assert_called_once()
            # NEM-3744: Cache invalidation is now deferred to background task
            mock_background_tasks.add_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_rule_severity_conversion(self) -> None:
        """Test updating rule severity converts enum correctly."""
        from backend.api.routes.alerts import update_rule
        from backend.api.schemas.alerts import AlertRuleUpdate, AlertSeverity

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_background_tasks = MagicMock()

        mock_rule = create_mock_rule(
            id="rule-id",
            name="Test Rule",
            severity=ModelAlertSeverity.MEDIUM,
            risk_threshold=None,
        )

        rule_update = AlertRuleUpdate(severity=AlertSeverity.CRITICAL)

        with patch(
            "backend.api.routes.alerts.get_alert_rule_or_404", return_value=mock_rule, autospec=True
        ):
            await update_rule(
                rule_id="rule-id",
                rule_data=rule_update,
                background_tasks=mock_background_tasks,
                db=mock_db,
                cache=mock_cache,
            )

            assert mock_rule.severity == ModelAlertSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_update_rule_not_found(self) -> None:
        """Test updating non-existent rule raises 404."""
        from backend.api.routes.alerts import update_rule
        from backend.api.schemas.alerts import AlertRuleUpdate

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_background_tasks = MagicMock()

        rule_update = AlertRuleUpdate(enabled=False)

        with patch(
            "backend.api.routes.alerts.get_alert_rule_or_404",
            side_effect=HTTPException(status_code=404, detail="Rule not found"),
            autospec=True,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await update_rule(
                    rule_id="nonexistent",
                    rule_data=rule_update,
                    background_tasks=mock_background_tasks,
                    db=mock_db,
                    cache=mock_cache,
                )

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_rule_cache_invalidation_failure(self) -> None:
        """Test updating rule schedules background task even if cache would fail."""
        from backend.api.routes.alerts import update_rule
        from backend.api.schemas.alerts import AlertRuleUpdate

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_background_tasks = MagicMock()

        mock_rule = create_mock_rule(
            id="rule-id",
            name="Test Rule",
            severity=ModelAlertSeverity.MEDIUM,
            risk_threshold=None,
        )

        rule_update = AlertRuleUpdate(enabled=False)

        with patch(
            "backend.api.routes.alerts.get_alert_rule_or_404", return_value=mock_rule, autospec=True
        ):
            # Background task is scheduled (actual cache invalidation happens later)
            result = await update_rule(
                rule_id="rule-id",
                rule_data=rule_update,
                background_tasks=mock_background_tasks,
                db=mock_db,
                cache=mock_cache,
            )

            assert result.id == "rule-id"
            mock_db.commit.assert_called_once()
            mock_background_tasks.add_task.assert_called_once()


class TestDeleteRule:
    """Tests for DELETE /api/alerts/rules/{rule_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_rule_success(self) -> None:
        """Test deleting a rule returns 204 and removes rule."""
        from backend.api.routes.alerts import delete_rule

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_background_tasks = MagicMock()

        mock_rule = MagicMock(spec=AlertRule)
        mock_rule.id = "rule-to-delete"

        with patch(
            "backend.api.routes.alerts.get_alert_rule_or_404", return_value=mock_rule, autospec=True
        ):
            result = await delete_rule(
                rule_id="rule-to-delete",
                background_tasks=mock_background_tasks,
                db=mock_db,
                cache=mock_cache,
            )

            assert result is None  # 204 No Content
            mock_db.delete.assert_called_once_with(mock_rule)
            mock_db.commit.assert_called_once()
            # NEM-3744: Cache invalidation is now deferred to background task
            mock_background_tasks.add_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_rule_not_found(self) -> None:
        """Test deleting non-existent rule raises 404."""
        from backend.api.routes.alerts import delete_rule

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_background_tasks = MagicMock()

        with patch(
            "backend.api.routes.alerts.get_alert_rule_or_404",
            side_effect=HTTPException(status_code=404, detail="Rule not found"),
            autospec=True,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await delete_rule(
                    rule_id="nonexistent",
                    background_tasks=mock_background_tasks,
                    db=mock_db,
                    cache=mock_cache,
                )

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_rule_cache_invalidation_failure(self) -> None:
        """Test deleting rule schedules background task even if cache would fail."""
        from backend.api.routes.alerts import delete_rule

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_background_tasks = MagicMock()

        mock_rule = MagicMock(spec=AlertRule)
        mock_rule.id = "rule-to-delete"

        with patch(
            "backend.api.routes.alerts.get_alert_rule_or_404", return_value=mock_rule, autospec=True
        ):
            # Background task is scheduled (actual cache invalidation happens later)
            result = await delete_rule(
                rule_id="rule-to-delete",
                background_tasks=mock_background_tasks,
                db=mock_db,
                cache=mock_cache,
            )

            assert result is None
            mock_db.delete.assert_called_once()
            mock_db.commit.assert_called_once()
            mock_background_tasks.add_task.assert_called_once()


class TestTestRule:
    """Tests for POST /api/alerts/rules/{rule_id}/test endpoint."""

    @pytest.mark.asyncio
    async def test_test_rule_with_event_ids(self) -> None:
        """Test testing rule against specific event IDs."""
        from backend.api.routes.alerts import test_rule
        from backend.api.schemas.alerts import RuleTestRequest

        mock_db = AsyncMock()
        mock_engine = AsyncMock()

        mock_rule = MagicMock(spec=AlertRule)
        mock_rule.id = "rule-id"
        mock_rule.name = "Test Rule"

        # Mock events
        from backend.models.event import Event

        mock_event = MagicMock(spec=Event)
        mock_event.id = 1
        mock_event.camera_id = "cam1"

        mock_events_result = MagicMock()
        mock_events_result.scalars.return_value.all.return_value = [mock_event]

        mock_db.execute.return_value = mock_events_result

        # Mock engine test results
        mock_engine.test_rule_against_events.return_value = [
            {
                "event_id": 1,
                "camera_id": "cam1",
                "risk_score": 75,
                "object_types": ["person"],
                "matches": True,
                "matched_conditions": ["risk_score >= 70"],
                "started_at": "2025-01-01T00:00:00Z",
            }
        ]

        test_data = RuleTestRequest(event_ids=[1])

        with patch(
            "backend.api.routes.alerts.get_alert_rule_or_404", return_value=mock_rule, autospec=True
        ):
            result = await test_rule(
                rule_id="rule-id",
                test_data=test_data,
                db=mock_db,
                engine=mock_engine,
            )

            assert result.rule_id == "rule-id"
            assert result.rule_name == "Test Rule"
            assert result.events_tested == 1
            assert result.events_matched == 1
            assert result.match_rate == 1.0
            assert len(result.results) == 1

    @pytest.mark.asyncio
    async def test_test_rule_recent_events(self) -> None:
        """Test testing rule against recent events when no event_ids provided."""
        from backend.api.routes.alerts import test_rule
        from backend.api.schemas.alerts import RuleTestRequest

        mock_db = AsyncMock()
        mock_engine = AsyncMock()

        mock_rule = MagicMock(spec=AlertRule)
        mock_rule.id = "rule-id"
        mock_rule.name = "Test Rule"

        # Mock events
        from backend.models.event import Event

        mock_events = []
        for i in range(10):
            mock_event = MagicMock(spec=Event)
            mock_event.id = i
            mock_event.camera_id = f"cam{i}"
            mock_events.append(mock_event)

        mock_events_result = MagicMock()
        mock_events_result.scalars.return_value.all.return_value = mock_events

        mock_db.execute.return_value = mock_events_result

        # Mock engine test results
        mock_engine.test_rule_against_events.return_value = [
            {
                "event_id": i,
                "camera_id": f"cam{i}",
                "risk_score": 50,
                "object_types": [],
                "matches": False,
                "matched_conditions": [],
                "started_at": "2025-01-01T00:00:00Z",
            }
            for i in range(10)
        ]

        test_data = RuleTestRequest(limit=10)

        with patch(
            "backend.api.routes.alerts.get_alert_rule_or_404", return_value=mock_rule, autospec=True
        ):
            result = await test_rule(
                rule_id="rule-id",
                test_data=test_data,
                db=mock_db,
                engine=mock_engine,
            )

            assert result.events_tested == 10
            assert result.events_matched == 0
            assert result.match_rate == 0.0

    @pytest.mark.asyncio
    async def test_test_rule_no_events(self) -> None:
        """Test testing rule when no events exist."""
        from backend.api.routes.alerts import test_rule
        from backend.api.schemas.alerts import RuleTestRequest

        mock_db = AsyncMock()
        mock_engine = AsyncMock()

        mock_rule = MagicMock(spec=AlertRule)
        mock_rule.id = "rule-id"
        mock_rule.name = "Test Rule"

        # Mock empty events
        mock_events_result = MagicMock()
        mock_events_result.scalars.return_value.all.return_value = []

        mock_db.execute.return_value = mock_events_result

        test_data = RuleTestRequest(limit=10)

        with patch(
            "backend.api.routes.alerts.get_alert_rule_or_404", return_value=mock_rule, autospec=True
        ):
            result = await test_rule(
                rule_id="rule-id",
                test_data=test_data,
                db=mock_db,
                engine=mock_engine,
            )

            assert result.events_tested == 0
            assert result.events_matched == 0
            assert result.match_rate == 0.0
            assert result.results == []

    @pytest.mark.asyncio
    async def test_test_rule_match_rate_calculation(self) -> None:
        """Test match rate is calculated correctly."""
        from backend.api.routes.alerts import test_rule
        from backend.api.schemas.alerts import RuleTestRequest

        mock_db = AsyncMock()
        mock_engine = AsyncMock()

        mock_rule = MagicMock(spec=AlertRule)
        mock_rule.id = "rule-id"
        mock_rule.name = "Test Rule"

        # Mock events
        from backend.models.event import Event

        mock_events = []
        for i in range(5):
            mock_event = MagicMock(spec=Event)
            mock_event.id = i
            mock_event.camera_id = f"cam{i}"
            mock_events.append(mock_event)

        mock_events_result = MagicMock()
        mock_events_result.scalars.return_value.all.return_value = mock_events

        mock_db.execute.return_value = mock_events_result

        # Mock engine test results - 2 out of 5 match
        mock_engine.test_rule_against_events.return_value = [
            {
                "event_id": 0,
                "camera_id": "cam0",
                "risk_score": 80,
                "object_types": ["person"],
                "matches": True,
                "matched_conditions": ["risk_score >= 70"],
                "started_at": "2025-01-01T00:00:00Z",
            },
            {
                "event_id": 1,
                "camera_id": "cam1",
                "risk_score": 50,
                "object_types": [],
                "matches": False,
                "matched_conditions": [],
                "started_at": "2025-01-01T00:00:00Z",
            },
            {
                "event_id": 2,
                "camera_id": "cam2",
                "risk_score": 75,
                "object_types": ["person"],
                "matches": True,
                "matched_conditions": ["risk_score >= 70"],
                "started_at": "2025-01-01T00:00:00Z",
            },
            {
                "event_id": 3,
                "camera_id": "cam3",
                "risk_score": 40,
                "object_types": [],
                "matches": False,
                "matched_conditions": [],
                "started_at": "2025-01-01T00:00:00Z",
            },
            {
                "event_id": 4,
                "camera_id": "cam4",
                "risk_score": 30,
                "object_types": [],
                "matches": False,
                "matched_conditions": [],
                "started_at": "2025-01-01T00:00:00Z",
            },
        ]

        test_data = RuleTestRequest(limit=5)

        with patch(
            "backend.api.routes.alerts.get_alert_rule_or_404", return_value=mock_rule, autospec=True
        ):
            result = await test_rule(
                rule_id="rule-id",
                test_data=test_data,
                db=mock_db,
                engine=mock_engine,
            )

            assert result.events_tested == 5
            assert result.events_matched == 2
            assert result.match_rate == 0.4  # 2/5


class TestAcknowledgeAlert:
    """Tests for POST /api/alerts/{alert_id}/acknowledge endpoint."""

    @pytest.mark.asyncio
    async def test_acknowledge_alert_from_pending(self) -> None:
        """Test acknowledging alert from PENDING status."""
        from backend.api.routes.alerts import acknowledge_alert

        mock_db = AsyncMock()

        mock_alert = MagicMock(spec=Alert)
        mock_alert.id = "alert-id"
        mock_alert.event_id = 1
        mock_alert.rule_id = "rule-id"
        mock_alert.severity = ModelAlertSeverity.HIGH
        mock_alert.status = AlertStatusEnum.PENDING
        mock_alert.created_at = datetime(2025, 1, 1, tzinfo=UTC)
        mock_alert.updated_at = datetime(2025, 1, 1, tzinfo=UTC)
        mock_alert.delivered_at = None
        mock_alert.channels = []
        mock_alert.dedup_key = "cam1:rule-id"
        mock_alert.alert_metadata = {}
        mock_alert.to_dict.return_value = {
            "id": "alert-id",
            "event_id": 1,
            "rule_id": "rule-id",
            "severity": "high",
            "status": "acknowledged",
            "created_at": datetime(2025, 1, 1, tzinfo=UTC),
            "updated_at": datetime(2025, 1, 1, tzinfo=UTC),
            "delivered_at": None,
            "channels": [],
            "dedup_key": "cam1:rule-id",
            "metadata": {},
        }

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_alert
        mock_db.execute.return_value = mock_result

        with patch(
            "backend.api.routes.alerts.EventBroadcaster.get_instance", autospec=True
        ) as mock_broadcaster:
            mock_broadcaster_instance = AsyncMock()
            mock_broadcaster_instance.broadcast_metrics = MagicMock()
            mock_broadcaster.return_value = mock_broadcaster_instance

            mock_background_tasks = MagicMock()
            result = await acknowledge_alert(
                alert_id="alert-id", background_tasks=mock_background_tasks, db=mock_db
            )

            assert result.id == "alert-id"
            assert mock_alert.status == AlertStatusEnum.ACKNOWLEDGED
            mock_db.commit.assert_called_once()
            # NEM-2582: Broadcast now uses background task instead of direct call
            # NEM-3624: Webhook triggering is also added as background task
            assert mock_background_tasks.add_task.call_count == 2

    @pytest.mark.asyncio
    async def test_acknowledge_alert_from_delivered(self) -> None:
        """Test acknowledging alert from DELIVERED status."""
        from backend.api.routes.alerts import acknowledge_alert

        mock_db = AsyncMock()

        mock_alert = MagicMock(spec=Alert)
        mock_alert.id = "alert-id"
        mock_alert.event_id = 1
        mock_alert.rule_id = "rule-id"
        mock_alert.severity = ModelAlertSeverity.HIGH
        mock_alert.status = AlertStatusEnum.DELIVERED
        mock_alert.created_at = datetime(2025, 1, 1, tzinfo=UTC)
        mock_alert.updated_at = datetime(2025, 1, 1, tzinfo=UTC)
        mock_alert.delivered_at = datetime(2025, 1, 1, 0, 1, tzinfo=UTC)
        mock_alert.channels = ["pushover"]
        mock_alert.dedup_key = "cam1:rule-id"
        mock_alert.alert_metadata = {}
        mock_alert.to_dict.return_value = {
            "id": "alert-id",
            "event_id": 1,
            "rule_id": "rule-id",
            "severity": "high",
            "status": "acknowledged",
            "created_at": datetime(2025, 1, 1, tzinfo=UTC),
            "updated_at": datetime(2025, 1, 1, tzinfo=UTC),
            "delivered_at": datetime(2025, 1, 1, 0, 1, tzinfo=UTC),
            "channels": ["pushover"],
            "dedup_key": "cam1:rule-id",
            "metadata": {},
        }

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_alert
        mock_db.execute.return_value = mock_result

        with patch(
            "backend.api.routes.alerts.EventBroadcaster.get_instance", autospec=True
        ) as mock_broadcaster:
            mock_broadcaster_instance = AsyncMock()
            mock_broadcaster_instance.broadcast_metrics = MagicMock()
            mock_broadcaster.return_value = mock_broadcaster_instance

            mock_background_tasks = MagicMock()
            result = await acknowledge_alert(
                alert_id="alert-id", background_tasks=mock_background_tasks, db=mock_db
            )

            assert mock_alert.status == AlertStatusEnum.ACKNOWLEDGED
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_acknowledge_alert_invalid_status(self) -> None:
        """Test acknowledging alert with invalid status raises 409."""
        from backend.api.routes.alerts import acknowledge_alert

        mock_db = AsyncMock()

        mock_alert = MagicMock(spec=Alert)
        mock_alert.id = "alert-id"
        mock_alert.status = AlertStatusEnum.DISMISSED

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_alert
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await acknowledge_alert(alert_id="alert-id", background_tasks=MagicMock(), db=mock_db)

        assert exc_info.value.status_code == 409
        assert "cannot be acknowledged" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_acknowledge_alert_not_found(self) -> None:
        """Test acknowledging non-existent alert raises 404."""
        from backend.api.routes.alerts import acknowledge_alert

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await acknowledge_alert(
                alert_id="nonexistent", background_tasks=MagicMock(), db=mock_db
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_acknowledge_alert_broadcast_failure(self) -> None:
        """Test acknowledging alert continues when broadcast fails."""
        from backend.api.routes.alerts import acknowledge_alert

        mock_db = AsyncMock()

        mock_alert = MagicMock(spec=Alert)
        mock_alert.id = "alert-id"
        mock_alert.event_id = 1
        mock_alert.rule_id = "rule-id"
        mock_alert.severity = ModelAlertSeverity.HIGH
        mock_alert.status = AlertStatusEnum.PENDING
        mock_alert.created_at = datetime(2025, 1, 1, tzinfo=UTC)
        mock_alert.updated_at = datetime(2025, 1, 1, tzinfo=UTC)
        mock_alert.delivered_at = None
        mock_alert.channels = []
        mock_alert.dedup_key = "cam1:rule-id"
        mock_alert.alert_metadata = {}
        mock_alert.to_dict.return_value = {
            "id": "alert-id",
            "event_id": 1,
            "rule_id": "rule-id",
            "severity": "high",
            "status": "acknowledged",
            "created_at": datetime(2025, 1, 1, tzinfo=UTC),
            "updated_at": datetime(2025, 1, 1, tzinfo=UTC),
            "delivered_at": None,
            "channels": [],
            "dedup_key": "cam1:rule-id",
            "metadata": {},
        }

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_alert
        mock_db.execute.return_value = mock_result

        # NEM-2582: Broadcast now uses background task, test that broadcaster failure
        # doesn't block the request - simulate RuntimeError from get_instance
        with patch(
            "backend.api.routes.alerts.EventBroadcaster.get_instance", autospec=True
        ) as mock_broadcaster:
            mock_broadcaster.side_effect = RuntimeError("Broadcaster not initialized")

            # Should not raise exception, just log warning
            result = await acknowledge_alert(
                alert_id="alert-id", background_tasks=MagicMock(), db=mock_db
            )

            assert result.id == "alert-id"
            assert mock_alert.status == AlertStatusEnum.ACKNOWLEDGED


class TestDismissAlert:
    """Tests for POST /api/alerts/{alert_id}/dismiss endpoint."""

    @pytest.mark.asyncio
    async def test_dismiss_alert_from_pending(self) -> None:
        """Test dismissing alert from PENDING status."""
        from backend.api.routes.alerts import dismiss_alert

        mock_db = AsyncMock()

        mock_alert = MagicMock(spec=Alert)
        mock_alert.id = "alert-id"
        mock_alert.event_id = 1
        mock_alert.rule_id = "rule-id"
        mock_alert.severity = ModelAlertSeverity.HIGH
        mock_alert.status = AlertStatusEnum.PENDING
        mock_alert.created_at = datetime(2025, 1, 1, tzinfo=UTC)
        mock_alert.updated_at = datetime(2025, 1, 1, tzinfo=UTC)
        mock_alert.delivered_at = None
        mock_alert.channels = []
        mock_alert.dedup_key = "cam1:rule-id"
        mock_alert.alert_metadata = {}
        mock_alert.to_dict.return_value = {
            "id": "alert-id",
            "event_id": 1,
            "rule_id": "rule-id",
            "severity": "high",
            "status": "dismissed",
            "created_at": datetime(2025, 1, 1, tzinfo=UTC),
            "updated_at": datetime(2025, 1, 1, tzinfo=UTC),
            "delivered_at": None,
            "channels": [],
            "dedup_key": "cam1:rule-id",
            "metadata": {},
        }

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_alert
        mock_db.execute.return_value = mock_result

        with patch(
            "backend.api.routes.alerts.EventBroadcaster.get_instance", autospec=True
        ) as mock_broadcaster:
            mock_broadcaster_instance = AsyncMock()
            mock_broadcaster_instance.broadcast_metrics = MagicMock()
            mock_broadcaster.return_value = mock_broadcaster_instance

            mock_background_tasks = MagicMock()
            result = await dismiss_alert(
                alert_id="alert-id", background_tasks=mock_background_tasks, db=mock_db
            )

            assert result.id == "alert-id"
            assert mock_alert.status == AlertStatusEnum.DISMISSED
            mock_db.commit.assert_called_once()
            # NEM-2582: Broadcast now uses background task instead of direct call
            # NEM-3624: Webhook triggering is also added as background task
            assert mock_background_tasks.add_task.call_count == 2

    @pytest.mark.asyncio
    async def test_dismiss_alert_from_delivered(self) -> None:
        """Test dismissing alert from DELIVERED status."""
        from backend.api.routes.alerts import dismiss_alert

        mock_db = AsyncMock()

        mock_alert = MagicMock(spec=Alert)
        mock_alert.id = "alert-id"
        mock_alert.event_id = 1
        mock_alert.rule_id = "rule-id"
        mock_alert.severity = ModelAlertSeverity.HIGH
        mock_alert.status = AlertStatusEnum.DELIVERED
        mock_alert.created_at = datetime(2025, 1, 1, tzinfo=UTC)
        mock_alert.updated_at = datetime(2025, 1, 1, tzinfo=UTC)
        mock_alert.delivered_at = datetime(2025, 1, 1, 0, 1, tzinfo=UTC)
        mock_alert.channels = ["pushover"]
        mock_alert.dedup_key = "cam1:rule-id"
        mock_alert.alert_metadata = {}
        mock_alert.to_dict.return_value = {
            "id": "alert-id",
            "event_id": 1,
            "rule_id": "rule-id",
            "severity": "high",
            "status": "dismissed",
            "created_at": datetime(2025, 1, 1, tzinfo=UTC),
            "updated_at": datetime(2025, 1, 1, tzinfo=UTC),
            "delivered_at": datetime(2025, 1, 1, 0, 1, tzinfo=UTC),
            "channels": ["pushover"],
            "dedup_key": "cam1:rule-id",
            "metadata": {},
        }

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_alert
        mock_db.execute.return_value = mock_result

        with patch(
            "backend.api.routes.alerts.EventBroadcaster.get_instance", autospec=True
        ) as mock_broadcaster:
            mock_broadcaster_instance = AsyncMock()
            mock_broadcaster_instance.broadcast_metrics = MagicMock()
            mock_broadcaster.return_value = mock_broadcaster_instance

            mock_background_tasks = MagicMock()
            result = await dismiss_alert(
                alert_id="alert-id", background_tasks=mock_background_tasks, db=mock_db
            )

            assert mock_alert.status == AlertStatusEnum.DISMISSED
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_dismiss_alert_from_acknowledged(self) -> None:
        """Test dismissing alert from ACKNOWLEDGED status."""
        from backend.api.routes.alerts import dismiss_alert

        mock_db = AsyncMock()

        mock_alert = MagicMock(spec=Alert)
        mock_alert.id = "alert-id"
        mock_alert.event_id = 1
        mock_alert.rule_id = "rule-id"
        mock_alert.severity = ModelAlertSeverity.HIGH
        mock_alert.status = AlertStatusEnum.ACKNOWLEDGED
        mock_alert.created_at = datetime(2025, 1, 1, tzinfo=UTC)
        mock_alert.updated_at = datetime(2025, 1, 1, tzinfo=UTC)
        mock_alert.delivered_at = None
        mock_alert.channels = []
        mock_alert.dedup_key = "cam1:rule-id"
        mock_alert.alert_metadata = {}
        mock_alert.to_dict.return_value = {
            "id": "alert-id",
            "event_id": 1,
            "rule_id": "rule-id",
            "severity": "high",
            "status": "dismissed",
            "created_at": datetime(2025, 1, 1, tzinfo=UTC),
            "updated_at": datetime(2025, 1, 1, tzinfo=UTC),
            "delivered_at": None,
            "channels": [],
            "dedup_key": "cam1:rule-id",
            "metadata": {},
        }

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_alert
        mock_db.execute.return_value = mock_result

        with patch(
            "backend.api.routes.alerts.EventBroadcaster.get_instance", autospec=True
        ) as mock_broadcaster:
            mock_broadcaster_instance = AsyncMock()
            mock_broadcaster_instance.broadcast_metrics = MagicMock()
            mock_broadcaster.return_value = mock_broadcaster_instance

            mock_background_tasks = MagicMock()
            result = await dismiss_alert(
                alert_id="alert-id", background_tasks=mock_background_tasks, db=mock_db
            )

            assert mock_alert.status == AlertStatusEnum.DISMISSED
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_dismiss_alert_already_dismissed(self) -> None:
        """Test dismissing already dismissed alert raises 409."""
        from backend.api.routes.alerts import dismiss_alert

        mock_db = AsyncMock()

        mock_alert = MagicMock(spec=Alert)
        mock_alert.id = "alert-id"
        mock_alert.status = AlertStatusEnum.DISMISSED

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_alert
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await dismiss_alert(alert_id="alert-id", background_tasks=MagicMock(), db=mock_db)

        assert exc_info.value.status_code == 409
        assert "already dismissed" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_dismiss_alert_not_found(self) -> None:
        """Test dismissing non-existent alert raises 404."""
        from backend.api.routes.alerts import dismiss_alert

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await dismiss_alert(alert_id="nonexistent", background_tasks=MagicMock(), db=mock_db)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_dismiss_alert_broadcast_failure(self) -> None:
        """Test dismissing alert continues when broadcast fails."""
        from backend.api.routes.alerts import dismiss_alert

        mock_db = AsyncMock()

        mock_alert = MagicMock(spec=Alert)
        mock_alert.id = "alert-id"
        mock_alert.event_id = 1
        mock_alert.rule_id = "rule-id"
        mock_alert.severity = ModelAlertSeverity.HIGH
        mock_alert.status = AlertStatusEnum.PENDING
        mock_alert.created_at = datetime(2025, 1, 1, tzinfo=UTC)
        mock_alert.updated_at = datetime(2025, 1, 1, tzinfo=UTC)
        mock_alert.delivered_at = None
        mock_alert.channels = []
        mock_alert.dedup_key = "cam1:rule-id"
        mock_alert.alert_metadata = {}
        mock_alert.to_dict.return_value = {
            "id": "alert-id",
            "event_id": 1,
            "rule_id": "rule-id",
            "severity": "high",
            "status": "dismissed",
            "created_at": datetime(2025, 1, 1, tzinfo=UTC),
            "updated_at": datetime(2025, 1, 1, tzinfo=UTC),
            "delivered_at": None,
            "channels": [],
            "dedup_key": "cam1:rule-id",
            "metadata": {},
        }

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_alert
        mock_db.execute.return_value = mock_result

        # NEM-2582: Broadcast now uses background task, test that broadcaster failure
        # doesn't block the request - simulate RuntimeError from get_instance
        with patch(
            "backend.api.routes.alerts.EventBroadcaster.get_instance", autospec=True
        ) as mock_broadcaster:
            mock_broadcaster.side_effect = RuntimeError("Broadcaster not initialized")

            # Should not raise exception, just log warning
            result = await dismiss_alert(
                alert_id="alert-id", background_tasks=MagicMock(), db=mock_db
            )

            assert result.id == "alert-id"
            assert mock_alert.status == AlertStatusEnum.DISMISSED


# =============================================================================
# Consolidated from backend/tests/unit/routes/test_alerts_routes.py (B4.1 step 2)
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
def mock_cache_service() -> AsyncMock:
    """Create a mock cache service for unit tests."""
    cache = AsyncMock()
    cache.invalidate_alerts = AsyncMock(return_value=1)
    return cache


@pytest.fixture
def sample_rule() -> AlertRule:
    """Create a sample alert rule for testing."""
    import uuid

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
        dedup_key_template="default:{camera_id}",
        cooldown_seconds=300,
        channels=["email"],
        dwell_time_enabled=False,
        created_at=datetime(2025, 12, 23, 10, 0, 0),
        updated_at=datetime(2025, 12, 23, 10, 0, 0),
    )


class TestAlertRuleResponseValidation:
    """Tests for AlertRuleResponse.model_validate with from_attributes."""

    def test_model_validate_with_enum_severity(self, sample_rule: AlertRule) -> None:
        """Test conversion with enum severity using model_validate."""
        from backend.api.schemas.alerts import AlertRuleResponse

        result = AlertRuleResponse.model_validate(sample_rule)

        assert result.id == sample_rule.id
        assert result.name == sample_rule.name
        assert result.severity == AlertSeverity.HIGH

    def test_model_validate_with_string_severity(self) -> None:
        """Test conversion with string severity using model_validate."""
        import uuid

        from backend.api.schemas.alerts import AlertRuleResponse

        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Test Rule",
            severity="low",
            enabled=True,
            dedup_key_template="default",
            cooldown_seconds=300,
            channels=["email"],
            dwell_time_enabled=False,
            created_at=datetime(2025, 12, 23, 10, 0, 0),
            updated_at=datetime(2025, 12, 23, 10, 0, 0),
        )

        result = AlertRuleResponse.model_validate(rule)

        assert result.severity == AlertSeverity.LOW

    def test_model_validate_includes_all_fields(self, sample_rule: AlertRule) -> None:
        """Test that all required fields are included via model_validate."""
        from backend.api.schemas.alerts import AlertRuleResponse

        result = AlertRuleResponse.model_validate(sample_rule)

        assert result.id is not None
        assert result.name is not None
        assert result.enabled is not None
        assert result.severity is not None
        assert result.dedup_key_template is not None
        assert result.cooldown_seconds is not None
        assert result.channels is not None
        assert result.dwell_time_enabled is not None
        assert result.created_at is not None
        assert result.updated_at is not None


class TestApplyRuleUpdates:
    """Tests for _apply_rule_updates helper function."""

    def test_apply_simple_fields(self, sample_rule: AlertRule) -> None:
        """Test updating simple fields."""
        from backend.api.routes.alerts import _apply_rule_updates
        from backend.api.schemas.alerts import AlertRuleUpdate

        update_data = AlertRuleUpdate(name="New Name", enabled=False)
        update_dict = update_data.model_dump(exclude_unset=True)

        _apply_rule_updates(sample_rule, update_data, update_dict)

        assert sample_rule.name == "New Name"
        assert sample_rule.enabled is False

    def test_apply_severity_update(self, sample_rule: AlertRule) -> None:
        """Test updating severity field."""
        from backend.api.routes.alerts import _apply_rule_updates
        from backend.api.schemas.alerts import AlertRuleUpdate

        update_data = AlertRuleUpdate(severity=AlertSeverity.CRITICAL)
        update_dict = update_data.model_dump(exclude_unset=True)

        _apply_rule_updates(sample_rule, update_data, update_dict)

        assert sample_rule.severity == ModelAlertSeverity.CRITICAL

    def test_apply_schedule_update(self, sample_rule: AlertRule) -> None:
        """Test updating schedule field."""
        from backend.api.routes.alerts import _apply_rule_updates
        from backend.api.schemas.alerts import AlertRuleSchedule, AlertRuleUpdate

        schedule = AlertRuleSchedule(days_of_week=[1, 2, 3], start_hour=9, end_hour=17)
        update_data = AlertRuleUpdate(schedule=schedule)
        update_dict = update_data.model_dump(exclude_unset=True)

        _apply_rule_updates(sample_rule, update_data, update_dict)

        assert sample_rule.schedule is not None

    def test_apply_null_schedule_update(self, sample_rule: AlertRule) -> None:
        """Test clearing schedule field."""
        from backend.api.routes.alerts import _apply_rule_updates
        from backend.api.schemas.alerts import AlertRuleUpdate

        sample_rule.schedule = {"days_of_week": [0, 6]}
        update_data = AlertRuleUpdate(schedule=None)
        update_dict = {"schedule": None}

        _apply_rule_updates(sample_rule, update_data, update_dict)

        assert sample_rule.schedule is None

    def test_apply_conditions_update(self, sample_rule: AlertRule) -> None:
        """Test updating conditions field."""
        from backend.api.routes.alerts import _apply_rule_updates
        from backend.api.schemas.alerts import AlertRuleConditions, AlertRuleUpdate

        conditions = AlertRuleConditions(
            logic="and",
            conditions=[{"field": "risk_score", "operator": ">=", "value": 80}],
        )
        update_data = AlertRuleUpdate(conditions=conditions)
        update_dict = update_data.model_dump(exclude_unset=True)

        _apply_rule_updates(sample_rule, update_data, update_dict)

        assert sample_rule.conditions is not None


class TestCacheInvalidation:
    """Tests for cache invalidation on alert rule mutation endpoints."""

    @pytest.fixture
    def client_with_cache(
        self, mock_db_session: AsyncMock, mock_cache_service: AsyncMock
    ) -> object:
        """Create a test client with mocked dependencies including cache."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from backend.api.dependencies import get_cache_service_dep
        from backend.api.routes.alerts import router
        from backend.core.database import get_db

        app = FastAPI()
        app.include_router(router)

        async def override_get_db():
            yield mock_db_session

        async def override_get_cache():
            yield mock_cache_service

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_cache_service_dep] = override_get_cache

        with TestClient(app) as test_client:
            yield test_client

    def test_create_rule_invalidates_cache(
        self,
        client_with_cache: object,
        mock_db_session: AsyncMock,
        mock_cache_service: AsyncMock,
    ) -> None:
        """Test that creating a rule invalidates alert caches."""
        import uuid

        from backend.core.constants import CacheInvalidationReason

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

        response = client_with_cache.post("/api/alerts/rules", json=rule_data)  # type: ignore[attr-defined]

        assert response.status_code == 201
        mock_cache_service.invalidate_alerts.assert_called_once_with(
            reason=CacheInvalidationReason.ALERT_RULE_CREATED
        )

    def test_update_rule_invalidates_cache(
        self,
        client_with_cache: object,
        mock_db_session: AsyncMock,
        mock_cache_service: AsyncMock,
        sample_rule: AlertRule,
    ) -> None:
        """Test that updating a rule invalidates alert caches."""
        from backend.core.constants import CacheInvalidationReason

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_rule
        mock_db_session.execute.return_value = mock_result

        response = client_with_cache.put(  # type: ignore[attr-defined]
            f"/api/alerts/rules/{sample_rule.id}",
            json={"name": "Updated Name"},
        )

        assert response.status_code == 200
        mock_cache_service.invalidate_alerts.assert_called_once_with(
            reason=CacheInvalidationReason.ALERT_RULE_UPDATED
        )

    def test_delete_rule_invalidates_cache(
        self,
        client_with_cache: object,
        mock_db_session: AsyncMock,
        mock_cache_service: AsyncMock,
        sample_rule: AlertRule,
    ) -> None:
        """Test that deleting a rule invalidates alert caches."""
        from backend.core.constants import CacheInvalidationReason

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_rule
        mock_db_session.execute.return_value = mock_result

        response = client_with_cache.delete(f"/api/alerts/rules/{sample_rule.id}")  # type: ignore[attr-defined]

        assert response.status_code == 204
        mock_cache_service.invalidate_alerts.assert_called_once_with(
            reason=CacheInvalidationReason.ALERT_RULE_DELETED
        )

    def test_cache_invalidation_failure_does_not_fail_request(
        self,
        client_with_cache: object,
        mock_db_session: AsyncMock,
        mock_cache_service: AsyncMock,
    ) -> None:
        """Test that cache invalidation failure does not cause the request to fail."""
        import uuid

        async def mock_refresh(rule):
            rule.id = str(uuid.uuid4())
            rule.created_at = datetime(2025, 12, 23, 10, 0, 0)
            rule.updated_at = datetime(2025, 12, 23, 10, 0, 0)
            rule.dedup_key_template = rule.dedup_key_template or "default"

        mock_db_session.refresh = mock_refresh
        mock_cache_service.invalidate_alerts.side_effect = Exception("Redis connection error")

        rule_data = {
            "name": "Test Rule",
            "severity": "high",
            "risk_threshold": 70,
            "enabled": True,
        }

        response = client_with_cache.post("/api/alerts/rules", json=rule_data)  # type: ignore[attr-defined]

        assert response.status_code == 201


class TestOptimisticLocking:
    """Tests for optimistic locking on alert state changes."""

    @pytest.fixture
    def alert_client(self, mock_db_session: AsyncMock) -> object:
        """Create a test client with mocked dependencies for alert instance endpoints."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from backend.api.routes.alerts import alerts_instance_router
        from backend.core.database import get_db

        app = FastAPI()
        app.include_router(alerts_instance_router)

        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as test_client:
            yield test_client

    @pytest.fixture
    def sample_alert(self) -> Alert:
        """Create a sample alert for testing."""
        import uuid

        return Alert(
            id=str(uuid.uuid4()),
            event_id=1,
            rule_id=str(uuid.uuid4()),
            severity=ModelAlertSeverity.HIGH,
            status=AlertStatusEnum.PENDING,
            dedup_key="test:dedup:key",
            channels=["push"],
            alert_metadata={"test": "data"},
            created_at=datetime(2025, 12, 23, 10, 0, 0),
            updated_at=datetime(2025, 12, 23, 10, 0, 0),
            version_id=1,
        )

    def test_acknowledge_concurrent_modification_returns_409(
        self, alert_client: object, mock_db_session: AsyncMock, sample_alert: Alert
    ) -> None:
        """Test concurrent modification during acknowledge returns 409 Conflict."""
        from sqlalchemy.orm.exc import StaleDataError

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_db_session.execute.return_value = mock_result
        mock_db_session.commit.side_effect = StaleDataError(
            "UPDATE statement on table 'alerts' expected to update 1 row(s); 0 were matched."
        )

        response = alert_client.post(f"/api/alerts/{sample_alert.id}/acknowledge")  # type: ignore[attr-defined]

        assert response.status_code == 409
        data = response.json()
        assert "modified by another request" in data["detail"].lower()
        mock_db_session.rollback.assert_called_once()

    def test_dismiss_concurrent_modification_returns_409(
        self, alert_client: object, mock_db_session: AsyncMock, sample_alert: Alert
    ) -> None:
        """Test concurrent modification during dismiss returns 409 Conflict."""
        from sqlalchemy.orm.exc import StaleDataError

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_db_session.execute.return_value = mock_result
        mock_db_session.commit.side_effect = StaleDataError(
            "UPDATE statement on table 'alerts' expected to update 1 row(s); 0 were matched."
        )

        response = alert_client.post(f"/api/alerts/{sample_alert.id}/dismiss")  # type: ignore[attr-defined]

        assert response.status_code == 409
        data = response.json()
        assert "modified by another request" in data["detail"].lower()
        mock_db_session.rollback.assert_called_once()
