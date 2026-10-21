"""Unit tests for AlertRule model condition fields (dwell_time and threat_detected).

R2a row 32 (F-220) retired the pose, action, and smoke/fire rule condition fields,
keeping the dwell_time and threat_detected (OD-7) fields.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import inspect

from backend.models import AlertRule, AlertSeverity


class TestAlertRuleNewFields:
    """Tests for kept AlertRule condition fields."""

    def test_alert_rule_has_dwell_time_fields(self) -> None:
        """Test that AlertRule model has dwell_time fields."""
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Loitering Alert",
            enabled=True,
            severity=AlertSeverity.MEDIUM,
            dwell_threshold_seconds=30,
            exclude_household_members=False,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert hasattr(rule, "dwell_threshold_seconds")
        assert rule.dwell_threshold_seconds == 30
        assert hasattr(rule, "exclude_household_members")
        assert rule.exclude_household_members is False

    def test_alert_rule_has_threat_detection_fields(self) -> None:
        """Test that AlertRule model has threat_detection fields."""
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Weapon Detection",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            threat_detection_enabled=True,
            threat_types=["gun", "knife"],
            threat_min_severity="high",
            threat_confidence_threshold=0.90,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert hasattr(rule, "threat_detection_enabled")
        assert rule.threat_detection_enabled is True
        assert hasattr(rule, "threat_types")
        assert rule.threat_types == ["gun", "knife"]
        assert hasattr(rule, "threat_min_severity")
        assert rule.threat_min_severity == "high"
        assert hasattr(rule, "threat_confidence_threshold")
        assert rule.threat_confidence_threshold == 0.90


class TestAlertRuleFieldDefaults:
    """Tests for default values of kept AlertRule condition fields."""

    def test_dwell_threshold_seconds_defaults_to_none(self) -> None:
        """Test that dwell_threshold_seconds defaults to None (no condition)."""
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Default Dwell",
            enabled=True,
            severity=AlertSeverity.LOW,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert hasattr(rule, "dwell_threshold_seconds")
        assert rule.dwell_threshold_seconds is None

    def test_exclude_household_members_defaults_to_false(self) -> None:
        """Test that exclude_household_members defaults to False."""
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Default Household",
            enabled=True,
            severity=AlertSeverity.LOW,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert hasattr(rule, "exclude_household_members")
        assert rule.exclude_household_members is False

    def test_threat_detection_enabled_defaults_to_false(self) -> None:
        """Test that threat_detection_enabled defaults to False."""
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Default Threat",
            enabled=True,
            severity=AlertSeverity.LOW,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert hasattr(rule, "threat_detection_enabled")
        assert rule.threat_detection_enabled is False


class TestAlertRuleFieldTypes:
    """Tests for field types and nullability of kept AlertRule fields."""

    def test_dwell_threshold_seconds_is_nullable_integer(self) -> None:
        """Test that dwell_threshold_seconds is a nullable integer field."""
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Null Dwell",
            enabled=True,
            severity=AlertSeverity.LOW,
            dwell_threshold_seconds=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert rule.dwell_threshold_seconds is None

    def test_threat_types_is_json_array(self) -> None:
        """Test that threat_types stores as JSON array."""
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="JSON Threat",
            enabled=True,
            severity=AlertSeverity.LOW,
            threat_types=["gun", "knife", "explosive"],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert isinstance(rule.threat_types, list)
        assert len(rule.threat_types) == 3

    def test_confidence_thresholds_are_floats(self) -> None:
        """Test that kept confidence threshold fields accept float values."""
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Float Confidence",
            enabled=True,
            severity=AlertSeverity.LOW,
            threat_confidence_threshold=0.90,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert isinstance(rule.threat_confidence_threshold, float)


class TestAlertRuleDatabaseColumns:
    """Tests for database column definitions of AlertRule fields."""

    def test_new_fields_have_database_columns(self) -> None:
        """Test that AlertRule mapper maps only the 24 kept columns (F-220 retired 7)."""
        mapper = inspect(AlertRule)
        column_names = [column.key for column in mapper.columns]

        expected_columns = [
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
            "dwell_time_enabled",
            "conditions",
            "dwell_threshold_seconds",
            "exclude_household_members",
            "threat_detection_enabled",
            "threat_types",
            "threat_min_severity",
            "threat_confidence_threshold",
            "dedup_key_template",
            "cooldown_seconds",
            "channels",
            "created_at",
            "updated_at",
        ]

        assert column_names == expected_columns

    def test_json_fields_use_correct_type(self) -> None:
        """Test that JSON array fields use JSON or JSONB column type."""
        mapper = inspect(AlertRule)
        column = mapper.columns["threat_types"]
        assert column.type.__class__.__name__ in ["JSON", "JSONB"]

    def test_boolean_fields_have_correct_defaults(self) -> None:
        """Test that boolean fields have correct default values in database."""
        mapper = inspect(AlertRule)

        exclude_household = mapper.columns["exclude_household_members"]
        assert exclude_household.default is not None or exclude_household.server_default is not None

        threat_enabled = mapper.columns["threat_detection_enabled"]
        assert threat_enabled.default is not None or threat_enabled.server_default is not None


class TestAlertRuleAllNewFieldsTogether:
    """Tests for using all kept condition fields together in AlertRule."""

    def test_create_rule_with_all_new_fields(self) -> None:
        """Test creating AlertRule with all kept condition fields."""
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Comprehensive Security Rule",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            dwell_threshold_seconds=30,
            exclude_household_members=True,
            threat_detection_enabled=True,
            threat_types=["gun", "knife"],
            threat_min_severity="high",
            threat_confidence_threshold=0.90,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert rule.dwell_threshold_seconds == 30
        assert rule.exclude_household_members is True
        assert rule.threat_detection_enabled is True
        assert rule.threat_types == ["gun", "knife"]
        assert rule.threat_min_severity == "high"
        assert rule.threat_confidence_threshold == 0.90

    def test_repr_includes_new_fields(self) -> None:
        """Test that AlertRule __repr__ handles condition fields."""
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Test Rule",
            enabled=True,
            severity=AlertSeverity.HIGH,
            dwell_threshold_seconds=30,
            threat_detection_enabled=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        repr_str = repr(rule)
        assert isinstance(repr_str, str)
        assert "AlertRule" in repr_str
        assert "Test Rule" in repr_str
