"""Unit tests for Alert Rule Condition Types schema validation (dwell_time and threat_detected).

R2a row 32 (F-220) retired the pose, action, and smoke/fire rule condition fields,
keeping dwell_time and threat_detected (OD-7).
"""

import pytest
from pydantic import ValidationError

from backend.api.schemas.alerts import (
    AlertRuleCreate,
    AlertRuleResponse,
    AlertRuleUpdate,
    AlertSeverity,
)


class TestDwellTimeSchemaValidation:
    """Tests for dwell_time condition schema validation."""

    def test_dwell_time_schema_validation_valid(self) -> None:
        """Test that valid dwell_time fields pass validation."""
        rule = AlertRuleCreate(
            name="Loitering Alert",
            severity=AlertSeverity.MEDIUM,
            dwell_threshold_seconds=30,
            exclude_household_members=False,
        )

        assert rule.dwell_threshold_seconds == 30
        assert rule.exclude_household_members is False

    def test_dwell_time_threshold_must_be_positive(self) -> None:
        """Test that dwell_threshold_seconds must be >= 0."""
        with pytest.raises(ValidationError) as exc_info:
            AlertRuleCreate(
                name="Invalid Loitering",
                severity=AlertSeverity.MEDIUM,
                dwell_threshold_seconds=-10,
            )

        errors = exc_info.value.errors()
        assert any(
            "dwell_threshold_seconds" in str(error["loc"])
            and "greater than or equal to 0" in str(error["msg"])
            for error in errors
        )

    def test_dwell_time_threshold_optional(self) -> None:
        """Test that dwell_threshold_seconds is optional (null = no dwell condition)."""
        rule = AlertRuleCreate(
            name="No Dwell Condition",
            severity=AlertSeverity.LOW,
        )

        assert rule.dwell_threshold_seconds is None

    def test_dwell_time_exclude_household_defaults_false(self) -> None:
        """Test that exclude_household_members defaults to False."""
        rule = AlertRuleCreate(
            name="Loitering Alert",
            severity=AlertSeverity.MEDIUM,
            dwell_threshold_seconds=30,
        )

        assert hasattr(rule, "exclude_household_members")
        assert rule.exclude_household_members is False

    def test_dwell_time_update_schema(self) -> None:
        """Test that dwell_time fields work in update schema."""
        update = AlertRuleUpdate(
            dwell_threshold_seconds=60,
            exclude_household_members=True,
        )

        assert update.dwell_threshold_seconds == 60
        assert update.exclude_household_members is True


class TestThreatDetectedSchemaValidation:
    """Tests for threat_detected condition schema validation."""

    def test_threat_detected_schema_validation_valid(self) -> None:
        """Test that valid threat detection fields pass validation."""
        rule = AlertRuleCreate(
            name="Weapon Detection",
            severity=AlertSeverity.CRITICAL,
            threat_detection_enabled=True,
            threat_types=["gun", "knife"],
            threat_min_severity="high",
            threat_confidence_threshold=0.90,
        )

        assert rule.threat_detection_enabled is True
        assert rule.threat_types == ["gun", "knife"]
        assert rule.threat_min_severity == "high"
        assert rule.threat_confidence_threshold == 0.90

    def test_threat_detection_enabled_defaults_false(self) -> None:
        """Test that threat_detection_enabled defaults to False."""
        rule = AlertRuleCreate(
            name="Normal Alert",
            severity=AlertSeverity.LOW,
        )

        assert hasattr(rule, "threat_detection_enabled")
        assert rule.threat_detection_enabled is False

    def test_threat_types_validates_allowed_values(self) -> None:
        """Test that threat_types validates against allowed threat types."""
        rule = AlertRuleCreate(
            name="Valid Threats",
            severity=AlertSeverity.CRITICAL,
            threat_detection_enabled=True,
            threat_types=["gun", "knife", "explosive"],
        )

        assert rule.threat_types == ["gun", "knife", "explosive"]

    def test_threat_min_severity_validates_allowed_values(self) -> None:
        """Test that threat_min_severity validates against allowed severities."""
        with pytest.raises(ValidationError) as exc_info:
            AlertRuleCreate(
                name="Invalid Severity",
                severity=AlertSeverity.CRITICAL,
                threat_detection_enabled=True,
                threat_min_severity="ultra_critical",
            )

        errors = exc_info.value.errors()
        assert any("threat_min_severity" in str(error["loc"]) for error in errors)

    def test_threat_confidence_range_validation(self) -> None:
        """Test that threat_confidence_threshold must be between 0.0 and 1.0."""
        with pytest.raises(ValidationError) as exc_info:
            AlertRuleCreate(
                name="Invalid Confidence",
                severity=AlertSeverity.CRITICAL,
                threat_detection_enabled=True,
                threat_confidence_threshold=2.0,
            )

        errors = exc_info.value.errors()
        assert any("threat_confidence_threshold" in str(error["loc"]) for error in errors)

    def test_threat_fields_optional(self) -> None:
        """Test that threat fields are optional when threat_detection_enabled=False."""
        rule = AlertRuleCreate(
            name="No Threats",
            severity=AlertSeverity.LOW,
            threat_detection_enabled=False,
        )

        assert rule.threat_detection_enabled is False
        assert rule.threat_types is None or rule.threat_types == []

    def test_threat_detection_update_schema(self) -> None:
        """Test that threat detection fields work in update schema."""
        update = AlertRuleUpdate(
            threat_detection_enabled=True,
            threat_types=["gun"],
            threat_min_severity="critical",
            threat_confidence_threshold=0.95,
        )

        assert update.threat_detection_enabled is True
        assert update.threat_types == ["gun"]
        assert update.threat_min_severity == "critical"
        assert update.threat_confidence_threshold == 0.95


class TestCombinedSchemaValidation:
    """Tests for combining kept condition types in schemas."""

    def test_all_new_conditions_in_single_rule(self) -> None:
        """Test that kept condition types can be combined and retired fields are absent."""
        expected_fields = {
            "name",
            "description",
            "enabled",
            "severity",
            "risk_threshold",
            "object_types",
            "camera_ids",
            "excluded_camera_ids",
            "alert_on_rejected",
            "zone_ids",
            "min_confidence",
            "schedule",
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
            "dwell_time_enabled",
        }
        assert set(AlertRuleCreate.model_fields) == expected_fields
        assert set(AlertRuleUpdate.model_fields) == expected_fields
        assert set(AlertRuleResponse.model_fields) == expected_fields | {
            "id",
            "created_at",
            "updated_at",
        }

        rule = AlertRuleCreate(
            name="Comprehensive Security Rule",
            severity=AlertSeverity.HIGH,
            dwell_threshold_seconds=30,
            threat_detection_enabled=True,
        )

        assert rule.dwell_threshold_seconds == 30
        assert rule.threat_detection_enabled is True

    def test_new_conditions_with_existing_conditions(self) -> None:
        """Test that new conditions work alongside existing conditions."""
        rule = AlertRuleCreate(
            name="Mixed Conditions",
            severity=AlertSeverity.HIGH,
            risk_threshold=70,
            camera_ids=["front_door"],
            min_confidence=0.8,
            dwell_threshold_seconds=30,
            threat_detection_enabled=True,
        )

        assert rule.risk_threshold == 70
        assert rule.camera_ids == ["front_door"]
        assert rule.min_confidence == 0.8
        assert rule.dwell_threshold_seconds == 30
        assert rule.threat_detection_enabled is True

    def test_partial_update_with_new_conditions(self) -> None:
        """Test that partial updates work with condition fields."""
        update = AlertRuleUpdate(
            dwell_threshold_seconds=60,
        )

        assert update.dwell_threshold_seconds == 60
        assert update.threat_detection_enabled is None
