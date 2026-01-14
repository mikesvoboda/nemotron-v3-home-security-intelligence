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
from backend.core.constants import CacheInvalidationReason
from backend.models.alert import Alert, AlertRule, AlertStatusEnum
from backend.models.alert import AlertSeverity as ModelAlertSeverity


class TestListRules:
    """Tests for GET /api/alerts/rules endpoint."""

    @pytest.mark.asyncio
    async def test_list_rules_no_filter(self) -> None:
        """Test listing all rules without filters."""
        from backend.api.routes.alerts import list_rules

        mock_db = AsyncMock()

        # Mock database query
        mock_rule = MagicMock(spec=AlertRule)
        mock_rule.id = "rule-1"
        mock_rule.name = "Test Rule"
        mock_rule.description = "Test description"
        mock_rule.enabled = True
        mock_rule.severity = ModelAlertSeverity.HIGH
        mock_rule.risk_threshold = 70
        mock_rule.object_types = ["person"]
        mock_rule.camera_ids = ["cam1"]
        mock_rule.zone_ids = None
        mock_rule.min_confidence = 0.8
        mock_rule.schedule = None
        mock_rule.conditions = None
        mock_rule.dedup_key_template = "{camera_id}:{rule_id}"
        mock_rule.cooldown_seconds = 300
        mock_rule.channels = ["pushover"]
        mock_rule.created_at = datetime(2025, 1, 1, tzinfo=UTC)
        mock_rule.updated_at = datetime(2025, 1, 1, tzinfo=UTC)

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

        # Mock rules query
        mock_rule = MagicMock(spec=AlertRule)
        mock_rule.id = "rule-enabled"
        mock_rule.name = "Enabled Rule"
        mock_rule.enabled = True
        mock_rule.severity = ModelAlertSeverity.MEDIUM
        mock_rule.risk_threshold = 50
        mock_rule.object_types = None
        mock_rule.camera_ids = None
        mock_rule.zone_ids = None
        mock_rule.min_confidence = None
        mock_rule.schedule = None
        mock_rule.conditions = None
        mock_rule.dedup_key_template = "{camera_id}:{rule_id}"
        mock_rule.cooldown_seconds = 300
        mock_rule.channels = []
        mock_rule.description = None
        mock_rule.created_at = datetime(2025, 1, 1, tzinfo=UTC)
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

        # Mock rules query
        mock_rule = MagicMock(spec=AlertRule)
        mock_rule.id = "rule-critical"
        mock_rule.name = "Critical Rule"
        mock_rule.enabled = True
        mock_rule.severity = ModelAlertSeverity.CRITICAL
        mock_rule.risk_threshold = 90
        mock_rule.object_types = ["person"]
        mock_rule.camera_ids = None
        mock_rule.zone_ids = None
        mock_rule.min_confidence = None
        mock_rule.schedule = None
        mock_rule.conditions = None
        mock_rule.dedup_key_template = "{camera_id}:{rule_id}"
        mock_rule.cooldown_seconds = 300
        mock_rule.channels = []
        mock_rule.description = None
        mock_rule.created_at = datetime(2025, 1, 1, tzinfo=UTC)
        mock_rule.updated_at = datetime(2025, 1, 1, tzinfo=UTC)

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

        # Mock rules query - return 10 rules
        mock_rules = []
        for i in range(10):
            mock_rule = MagicMock(spec=AlertRule)
            mock_rule.id = f"rule-{i}"
            mock_rule.name = f"Rule {i}"
            mock_rule.enabled = True
            mock_rule.severity = ModelAlertSeverity.MEDIUM
            mock_rule.risk_threshold = 50
            mock_rule.object_types = None
            mock_rule.camera_ids = None
            mock_rule.zone_ids = None
            mock_rule.min_confidence = None
            mock_rule.schedule = None
            mock_rule.conditions = None
            mock_rule.dedup_key_template = "{camera_id}:{rule_id}"
            mock_rule.cooldown_seconds = 300
            mock_rule.channels = []
            mock_rule.description = None
            mock_rule.created_at = datetime(2025, 1, 1, tzinfo=UTC)
            mock_rule.updated_at = datetime(2025, 1, 1, tzinfo=UTC)
            mock_rules.append(mock_rule)

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

        # Mock rules query - should be sorted alphabetically
        mock_rule_a = MagicMock(spec=AlertRule)
        mock_rule_a.id = "rule-a"
        mock_rule_a.name = "A Rule"
        mock_rule_a.enabled = True
        mock_rule_a.severity = ModelAlertSeverity.MEDIUM
        mock_rule_a.risk_threshold = 50
        mock_rule_a.object_types = None
        mock_rule_a.camera_ids = None
        mock_rule_a.zone_ids = None
        mock_rule_a.min_confidence = None
        mock_rule_a.schedule = None
        mock_rule_a.conditions = None
        mock_rule_a.dedup_key_template = "{camera_id}:{rule_id}"
        mock_rule_a.cooldown_seconds = 300
        mock_rule_a.channels = []
        mock_rule_a.description = None
        mock_rule_a.created_at = datetime(2025, 1, 1, tzinfo=UTC)
        mock_rule_a.updated_at = datetime(2025, 1, 1, tzinfo=UTC)

        mock_rule_b = MagicMock(spec=AlertRule)
        mock_rule_b.id = "rule-b"
        mock_rule_b.name = "B Rule"
        mock_rule_b.enabled = True
        mock_rule_b.severity = ModelAlertSeverity.HIGH
        mock_rule_b.risk_threshold = 70
        mock_rule_b.object_types = None
        mock_rule_b.camera_ids = None
        mock_rule_b.zone_ids = None
        mock_rule_b.min_confidence = None
        mock_rule_b.schedule = None
        mock_rule_b.conditions = None
        mock_rule_b.dedup_key_template = "{camera_id}:{rule_id}"
        mock_rule_b.cooldown_seconds = 300
        mock_rule_b.channels = []
        mock_rule_b.description = None
        mock_rule_b.created_at = datetime(2025, 1, 2, tzinfo=UTC)
        mock_rule_b.updated_at = datetime(2025, 1, 2, tzinfo=UTC)

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

        rule_data = AlertRuleCreate(
            name="Test Rule",
            severity=AlertSeverity.MEDIUM,
        )

        # Mock the created rule
        with patch("backend.api.routes.alerts.AlertRule") as mock_rule_class:
            mock_rule_instance = MagicMock(spec=AlertRule)
            mock_rule_instance.id = "new-rule-id"
            mock_rule_instance.name = "Test Rule"
            mock_rule_instance.description = None
            mock_rule_instance.enabled = True
            mock_rule_instance.severity = ModelAlertSeverity.MEDIUM
            mock_rule_instance.risk_threshold = None
            mock_rule_instance.object_types = None
            mock_rule_instance.camera_ids = None
            mock_rule_instance.zone_ids = None
            mock_rule_instance.min_confidence = None
            mock_rule_instance.schedule = None
            mock_rule_instance.conditions = None
            mock_rule_instance.dedup_key_template = "{camera_id}:{rule_id}"
            mock_rule_instance.cooldown_seconds = 300
            mock_rule_instance.channels = []
            mock_rule_instance.created_at = datetime(2025, 1, 1, tzinfo=UTC)
            mock_rule_instance.updated_at = datetime(2025, 1, 1, tzinfo=UTC)

            mock_rule_class.return_value = mock_rule_instance

            result = await create_rule(rule_data, db=mock_db, cache=mock_cache)

            assert result.id == "new-rule-id"
            assert result.name == "Test Rule"
            assert result.severity == AlertSeverity.MEDIUM
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            mock_cache.invalidate_alerts.assert_called_once_with(
                reason=CacheInvalidationReason.ALERT_RULE_CREATED
            )

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

        # Mock the created rule
        with patch("backend.api.routes.alerts.AlertRule") as mock_rule_class:
            mock_rule_instance = MagicMock(spec=AlertRule)
            mock_rule_instance.id = "night-rule-id"
            mock_rule_instance.name = "Night Alert"
            mock_rule_instance.description = None
            mock_rule_instance.enabled = True
            mock_rule_instance.severity = ModelAlertSeverity.HIGH
            mock_rule_instance.risk_threshold = 70
            mock_rule_instance.object_types = None
            mock_rule_instance.camera_ids = None
            mock_rule_instance.zone_ids = None
            mock_rule_instance.min_confidence = None
            mock_rule_instance.schedule = {
                "days": ["monday", "tuesday"],
                "start_time": "22:00",
                "end_time": "06:00",
                "timezone": "America/New_York",
            }
            mock_rule_instance.conditions = None
            mock_rule_instance.dedup_key_template = "{camera_id}:{rule_id}"
            mock_rule_instance.cooldown_seconds = 300
            mock_rule_instance.channels = []
            mock_rule_instance.created_at = datetime(2025, 1, 1, tzinfo=UTC)
            mock_rule_instance.updated_at = datetime(2025, 1, 1, tzinfo=UTC)

            mock_rule_class.return_value = mock_rule_instance

            result = await create_rule(rule_data, db=mock_db, cache=mock_cache)

            assert result.name == "Night Alert"
            assert result.schedule is not None
            mock_cache.invalidate_alerts.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_rule_severity_enum_conversion(self) -> None:
        """Test that severity is correctly converted from schema enum to model enum."""
        from backend.api.routes.alerts import create_rule
        from backend.api.schemas.alerts import AlertRuleCreate, AlertSeverity

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        rule_data = AlertRuleCreate(name="Critical Rule", severity=AlertSeverity.CRITICAL)

        with patch("backend.api.routes.alerts.AlertRule") as mock_rule_class:
            mock_rule_instance = MagicMock(spec=AlertRule)
            mock_rule_instance.id = "critical-rule"
            mock_rule_instance.name = "Critical Rule"
            mock_rule_instance.description = None
            mock_rule_instance.enabled = True
            mock_rule_instance.severity = ModelAlertSeverity.CRITICAL
            mock_rule_instance.risk_threshold = None
            mock_rule_instance.object_types = None
            mock_rule_instance.camera_ids = None
            mock_rule_instance.zone_ids = None
            mock_rule_instance.min_confidence = None
            mock_rule_instance.schedule = None
            mock_rule_instance.conditions = None
            mock_rule_instance.dedup_key_template = "{camera_id}:{rule_id}"
            mock_rule_instance.cooldown_seconds = 300
            mock_rule_instance.channels = []
            mock_rule_instance.created_at = datetime(2025, 1, 1, tzinfo=UTC)
            mock_rule_instance.updated_at = datetime(2025, 1, 1, tzinfo=UTC)

            mock_rule_class.return_value = mock_rule_instance

            result = await create_rule(rule_data, db=mock_db, cache=mock_cache)

            assert result.severity == AlertSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_create_rule_cache_invalidation_failure(self) -> None:
        """Test creating rule continues when cache invalidation fails."""
        from backend.api.routes.alerts import create_rule
        from backend.api.schemas.alerts import AlertRuleCreate, AlertSeverity

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_cache.invalidate_alerts.side_effect = Exception("Redis error")

        rule_data = AlertRuleCreate(name="Test Rule", severity=AlertSeverity.LOW)

        with patch("backend.api.routes.alerts.AlertRule") as mock_rule_class:
            mock_rule_instance = MagicMock(spec=AlertRule)
            mock_rule_instance.id = "rule-id"
            mock_rule_instance.name = "Test Rule"
            mock_rule_instance.description = None
            mock_rule_instance.enabled = True
            mock_rule_instance.severity = ModelAlertSeverity.LOW
            mock_rule_instance.risk_threshold = None
            mock_rule_instance.object_types = None
            mock_rule_instance.camera_ids = None
            mock_rule_instance.zone_ids = None
            mock_rule_instance.min_confidence = None
            mock_rule_instance.schedule = None
            mock_rule_instance.conditions = None
            mock_rule_instance.dedup_key_template = "{camera_id}:{rule_id}"
            mock_rule_instance.cooldown_seconds = 300
            mock_rule_instance.channels = []
            mock_rule_instance.created_at = datetime(2025, 1, 1, tzinfo=UTC)
            mock_rule_instance.updated_at = datetime(2025, 1, 1, tzinfo=UTC)

            mock_rule_class.return_value = mock_rule_instance

            # Should not raise exception, just log warning
            result = await create_rule(rule_data, db=mock_db, cache=mock_cache)

            assert result.id == "rule-id"
            mock_db.commit.assert_called_once()


class TestGetRule:
    """Tests for GET /api/alerts/rules/{rule_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_rule_success(self) -> None:
        """Test getting a rule by ID."""
        from backend.api.routes.alerts import get_rule

        mock_db = AsyncMock()

        mock_rule = MagicMock(spec=AlertRule)
        mock_rule.id = "test-rule-id"
        mock_rule.name = "Test Rule"
        mock_rule.description = "Test description"
        mock_rule.enabled = True
        mock_rule.severity = ModelAlertSeverity.HIGH
        mock_rule.risk_threshold = 70
        mock_rule.object_types = ["person"]
        mock_rule.camera_ids = ["cam1"]
        mock_rule.zone_ids = None
        mock_rule.min_confidence = 0.8
        mock_rule.schedule = None
        mock_rule.conditions = None
        mock_rule.dedup_key_template = "{camera_id}:{rule_id}"
        mock_rule.cooldown_seconds = 300
        mock_rule.channels = ["pushover"]
        mock_rule.created_at = datetime(2025, 1, 1, tzinfo=UTC)
        mock_rule.updated_at = datetime(2025, 1, 1, tzinfo=UTC)

        with patch("backend.api.routes.alerts.get_alert_rule_or_404", return_value=mock_rule):
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

        # Mock existing rule
        mock_rule = MagicMock(spec=AlertRule)
        mock_rule.id = "rule-id"
        mock_rule.name = "Original Name"
        mock_rule.description = "Original description"
        mock_rule.enabled = True
        mock_rule.severity = ModelAlertSeverity.MEDIUM
        mock_rule.risk_threshold = 50
        mock_rule.object_types = None
        mock_rule.camera_ids = None
        mock_rule.zone_ids = None
        mock_rule.min_confidence = None
        mock_rule.schedule = None
        mock_rule.conditions = None
        mock_rule.dedup_key_template = "{camera_id}:{rule_id}"
        mock_rule.cooldown_seconds = 300
        mock_rule.channels = []
        mock_rule.created_at = datetime(2025, 1, 1, tzinfo=UTC)
        mock_rule.updated_at = datetime(2025, 1, 1, tzinfo=UTC)

        rule_update = AlertRuleUpdate(enabled=False)

        with patch("backend.api.routes.alerts.get_alert_rule_or_404", return_value=mock_rule):
            result = await update_rule(
                rule_id="rule-id",
                rule_data=rule_update,
                db=mock_db,
                cache=mock_cache,
            )

            # Only enabled should be updated
            assert mock_rule.enabled is False
            mock_db.commit.assert_called_once()
            mock_cache.invalidate_alerts.assert_called_once_with(
                reason=CacheInvalidationReason.ALERT_RULE_UPDATED
            )

    @pytest.mark.asyncio
    async def test_update_rule_severity_conversion(self) -> None:
        """Test updating rule severity converts enum correctly."""
        from backend.api.routes.alerts import update_rule
        from backend.api.schemas.alerts import AlertRuleUpdate, AlertSeverity

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        mock_rule = MagicMock(spec=AlertRule)
        mock_rule.id = "rule-id"
        mock_rule.name = "Test Rule"
        mock_rule.severity = ModelAlertSeverity.MEDIUM
        mock_rule.description = None
        mock_rule.enabled = True
        mock_rule.risk_threshold = None
        mock_rule.object_types = None
        mock_rule.camera_ids = None
        mock_rule.zone_ids = None
        mock_rule.min_confidence = None
        mock_rule.schedule = None
        mock_rule.conditions = None
        mock_rule.dedup_key_template = "{camera_id}:{rule_id}"
        mock_rule.cooldown_seconds = 300
        mock_rule.channels = []
        mock_rule.created_at = datetime(2025, 1, 1, tzinfo=UTC)
        mock_rule.updated_at = datetime(2025, 1, 1, tzinfo=UTC)

        rule_update = AlertRuleUpdate(severity=AlertSeverity.CRITICAL)

        with patch("backend.api.routes.alerts.get_alert_rule_or_404", return_value=mock_rule):
            await update_rule(
                rule_id="rule-id",
                rule_data=rule_update,
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

        rule_update = AlertRuleUpdate(enabled=False)

        with patch(
            "backend.api.routes.alerts.get_alert_rule_or_404",
            side_effect=HTTPException(status_code=404, detail="Rule not found"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await update_rule(
                    rule_id="nonexistent",
                    rule_data=rule_update,
                    db=mock_db,
                    cache=mock_cache,
                )

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_rule_cache_invalidation_failure(self) -> None:
        """Test updating rule continues when cache invalidation fails."""
        from backend.api.routes.alerts import update_rule
        from backend.api.schemas.alerts import AlertRuleUpdate

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_cache.invalidate_alerts.side_effect = Exception("Redis error")

        mock_rule = MagicMock(spec=AlertRule)
        mock_rule.id = "rule-id"
        mock_rule.name = "Test Rule"
        mock_rule.enabled = True
        mock_rule.severity = ModelAlertSeverity.MEDIUM
        mock_rule.description = None
        mock_rule.risk_threshold = None
        mock_rule.object_types = None
        mock_rule.camera_ids = None
        mock_rule.zone_ids = None
        mock_rule.min_confidence = None
        mock_rule.schedule = None
        mock_rule.conditions = None
        mock_rule.dedup_key_template = "{camera_id}:{rule_id}"
        mock_rule.cooldown_seconds = 300
        mock_rule.channels = []
        mock_rule.created_at = datetime(2025, 1, 1, tzinfo=UTC)
        mock_rule.updated_at = datetime(2025, 1, 1, tzinfo=UTC)

        rule_update = AlertRuleUpdate(enabled=False)

        with patch("backend.api.routes.alerts.get_alert_rule_or_404", return_value=mock_rule):
            # Should not raise exception, just log warning
            result = await update_rule(
                rule_id="rule-id",
                rule_data=rule_update,
                db=mock_db,
                cache=mock_cache,
            )

            assert result.id == "rule-id"
            mock_db.commit.assert_called_once()


class TestDeleteRule:
    """Tests for DELETE /api/alerts/rules/{rule_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_rule_success(self) -> None:
        """Test deleting a rule returns 204 and removes rule."""
        from backend.api.routes.alerts import delete_rule

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        mock_rule = MagicMock(spec=AlertRule)
        mock_rule.id = "rule-to-delete"

        with patch("backend.api.routes.alerts.get_alert_rule_or_404", return_value=mock_rule):
            result = await delete_rule(rule_id="rule-to-delete", db=mock_db, cache=mock_cache)

            assert result is None  # 204 No Content
            mock_db.delete.assert_called_once_with(mock_rule)
            mock_db.commit.assert_called_once()
            mock_cache.invalidate_alerts.assert_called_once_with(
                reason=CacheInvalidationReason.ALERT_RULE_DELETED
            )

    @pytest.mark.asyncio
    async def test_delete_rule_not_found(self) -> None:
        """Test deleting non-existent rule raises 404."""
        from backend.api.routes.alerts import delete_rule

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        with patch(
            "backend.api.routes.alerts.get_alert_rule_or_404",
            side_effect=HTTPException(status_code=404, detail="Rule not found"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await delete_rule(rule_id="nonexistent", db=mock_db, cache=mock_cache)

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_rule_cache_invalidation_failure(self) -> None:
        """Test deleting rule continues when cache invalidation fails."""
        from backend.api.routes.alerts import delete_rule

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_cache.invalidate_alerts.side_effect = Exception("Redis error")

        mock_rule = MagicMock(spec=AlertRule)
        mock_rule.id = "rule-to-delete"

        with patch("backend.api.routes.alerts.get_alert_rule_or_404", return_value=mock_rule):
            # Should not raise exception, just log warning
            result = await delete_rule(rule_id="rule-to-delete", db=mock_db, cache=mock_cache)

            assert result is None
            mock_db.delete.assert_called_once()
            mock_db.commit.assert_called_once()


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

        with patch("backend.api.routes.alerts.get_alert_rule_or_404", return_value=mock_rule):
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

        with patch("backend.api.routes.alerts.get_alert_rule_or_404", return_value=mock_rule):
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

        with patch("backend.api.routes.alerts.get_alert_rule_or_404", return_value=mock_rule):
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

        with patch("backend.api.routes.alerts.get_alert_rule_or_404", return_value=mock_rule):
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

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_alert
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.alerts.EventBroadcaster.get_instance") as mock_broadcaster:
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
            mock_background_tasks.add_task.assert_called_once()

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

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_alert
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.alerts.EventBroadcaster.get_instance") as mock_broadcaster:
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

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_alert
        mock_db.execute.return_value = mock_result

        # NEM-2582: Broadcast now uses background task, test that broadcaster failure
        # doesn't block the request - simulate RuntimeError from get_instance
        with patch("backend.api.routes.alerts.EventBroadcaster.get_instance") as mock_broadcaster:
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

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_alert
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.alerts.EventBroadcaster.get_instance") as mock_broadcaster:
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
            mock_background_tasks.add_task.assert_called_once()

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

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_alert
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.alerts.EventBroadcaster.get_instance") as mock_broadcaster:
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

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_alert
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.alerts.EventBroadcaster.get_instance") as mock_broadcaster:
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

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_alert
        mock_db.execute.return_value = mock_result

        # NEM-2582: Broadcast now uses background task, test that broadcaster failure
        # doesn't block the request - simulate RuntimeError from get_instance
        with patch("backend.api.routes.alerts.EventBroadcaster.get_instance") as mock_broadcaster:
            mock_broadcaster.side_effect = RuntimeError("Broadcaster not initialized")

            # Should not raise exception, just log warning
            result = await dismiss_alert(
                alert_id="alert-id", background_tasks=MagicMock(), db=mock_db
            )

            assert result.id == "alert-id"
            assert mock_alert.status == AlertStatusEnum.DISMISSED
