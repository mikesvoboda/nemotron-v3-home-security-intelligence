"""Unit tests for new AlertRule model fields (TDD RED phase).

This module contains failing tests that define expected database model fields for:
1. dwell_time condition fields
2. pose_type condition fields
3. action_type condition fields
4. threat_detected condition fields
5. smoke_fire condition fields

These tests are written FIRST (TDD red phase) and will initially fail.
Implementation should follow in backend/models/alert.py.

Design reference: docs/plans/2026-02-01-platform-enhancement-strategy-design.md
Related issue: NEM-5084
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import inspect

from backend.models import AlertRule, AlertSeverity

# =============================================================================
# Model Field Existence Tests
# =============================================================================


class TestAlertRuleNewFields:
    """Tests for new AlertRule model fields."""

    def test_alert_rule_has_dwell_time_fields(self) -> None:
        """Test that AlertRule model has dwell_time fields.

        Expected fields:
        - dwell_threshold_seconds: Integer, nullable=True
        - exclude_household_members: Boolean, default=False, nullable=False
        """
        # Arrange & Act: Create AlertRule instance
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Loitering Alert",
            enabled=True,
            severity=AlertSeverity.MEDIUM,
            dwell_threshold_seconds=30,  # NEW FIELD - will fail until implemented
            exclude_household_members=False,  # NEW FIELD
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Assert: Fields should exist and have correct values
        assert hasattr(rule, "dwell_threshold_seconds")
        assert rule.dwell_threshold_seconds == 30
        assert hasattr(rule, "exclude_household_members")
        assert rule.exclude_household_members is False

    def test_alert_rule_has_pose_type_fields(self) -> None:
        """Test that AlertRule model has pose_type fields.

        Expected fields:
        - pose_types: JSON array, nullable=True
        - pose_confidence_threshold: Float, nullable=True
        """
        # Arrange & Act: Create AlertRule with pose_types
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Pose Detection",
            enabled=True,
            severity=AlertSeverity.HIGH,
            pose_types=["crouching", "lying_down"],  # NEW FIELD - will fail until implemented
            pose_confidence_threshold=0.85,  # NEW FIELD
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Assert: Fields should exist and have correct values
        assert hasattr(rule, "pose_types")
        assert rule.pose_types == ["crouching", "lying_down"]
        assert hasattr(rule, "pose_confidence_threshold")
        assert rule.pose_confidence_threshold == 0.85

    def test_alert_rule_has_action_type_fields(self) -> None:
        """Test that AlertRule model has action_type fields.

        Expected fields:
        - action_types: JSON array, nullable=True
        - action_confidence_threshold: Float, nullable=True
        """
        # Arrange & Act: Create AlertRule with action_types
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Action Detection",
            enabled=True,
            severity=AlertSeverity.MEDIUM,
            action_types=[
                "loitering",
                "peering_through_window",
            ],  # NEW FIELD - will fail until implemented
            action_confidence_threshold=0.80,  # NEW FIELD
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Assert: Fields should exist and have correct values
        assert hasattr(rule, "action_types")
        assert rule.action_types == ["loitering", "peering_through_window"]
        assert hasattr(rule, "action_confidence_threshold")
        assert rule.action_confidence_threshold == 0.80

    def test_alert_rule_has_threat_detection_fields(self) -> None:
        """Test that AlertRule model has threat_detection fields.

        Expected fields:
        - threat_detection_enabled: Boolean, default=False, nullable=False
        - threat_types: JSON array, nullable=True
        - threat_min_severity: String, nullable=True
        - threat_confidence_threshold: Float, nullable=True
        """
        # Arrange & Act: Create AlertRule with threat detection
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Weapon Detection",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            threat_detection_enabled=True,  # NEW FIELD - will fail until implemented
            threat_types=["gun", "knife"],  # NEW FIELD
            threat_min_severity="high",  # NEW FIELD
            threat_confidence_threshold=0.90,  # NEW FIELD
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Assert: Fields should exist and have correct values
        assert hasattr(rule, "threat_detection_enabled")
        assert rule.threat_detection_enabled is True
        assert hasattr(rule, "threat_types")
        assert rule.threat_types == ["gun", "knife"]
        assert hasattr(rule, "threat_min_severity")
        assert rule.threat_min_severity == "high"
        assert hasattr(rule, "threat_confidence_threshold")
        assert rule.threat_confidence_threshold == 0.90

    def test_alert_rule_has_smoke_fire_fields(self) -> None:
        """Test that AlertRule model has smoke_fire fields.

        Expected fields:
        - smoke_fire_detection_enabled: Boolean, default=False, nullable=False
        - smoke_fire_consecutive_required: Integer, default=2, nullable=False
        - smoke_fire_confidence_threshold: Float, nullable=True
        """
        # Arrange & Act: Create AlertRule with smoke_fire detection
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Fire Safety",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            smoke_fire_detection_enabled=True,  # NEW FIELD - will fail until implemented
            smoke_fire_consecutive_required=2,  # NEW FIELD
            smoke_fire_confidence_threshold=0.85,  # NEW FIELD
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Assert: Fields should exist and have correct values
        assert hasattr(rule, "smoke_fire_detection_enabled")
        assert rule.smoke_fire_detection_enabled is True
        assert hasattr(rule, "smoke_fire_consecutive_required")
        assert rule.smoke_fire_consecutive_required == 2
        assert hasattr(rule, "smoke_fire_confidence_threshold")
        assert rule.smoke_fire_confidence_threshold == 0.85


# =============================================================================
# Default Value Tests
# =============================================================================


class TestAlertRuleFieldDefaults:
    """Tests for default values of new AlertRule fields."""

    def test_dwell_threshold_seconds_defaults_to_none(self) -> None:
        """Test that dwell_threshold_seconds defaults to None (no condition)."""
        # Arrange & Act: Create rule without dwell_threshold_seconds
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Default Dwell",
            enabled=True,
            severity=AlertSeverity.LOW,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Assert: Should default to None
        assert hasattr(rule, "dwell_threshold_seconds")
        assert rule.dwell_threshold_seconds is None

    def test_exclude_household_members_defaults_to_false(self) -> None:
        """Test that exclude_household_members defaults to False."""
        # Arrange & Act: Create rule without exclude_household_members
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Default Household",
            enabled=True,
            severity=AlertSeverity.LOW,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Assert: Should default to False
        assert hasattr(rule, "exclude_household_members")
        assert rule.exclude_household_members is False

    def test_pose_types_defaults_to_none(self) -> None:
        """Test that pose_types defaults to None (no condition)."""
        # Arrange & Act: Create rule without pose_types
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Default Pose",
            enabled=True,
            severity=AlertSeverity.LOW,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Assert: Should default to None
        assert hasattr(rule, "pose_types")
        assert rule.pose_types is None

    def test_action_types_defaults_to_none(self) -> None:
        """Test that action_types defaults to None (no condition)."""
        # Arrange & Act: Create rule without action_types
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Default Action",
            enabled=True,
            severity=AlertSeverity.LOW,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Assert: Should default to None
        assert hasattr(rule, "action_types")
        assert rule.action_types is None

    def test_threat_detection_enabled_defaults_to_false(self) -> None:
        """Test that threat_detection_enabled defaults to False."""
        # Arrange & Act: Create rule without threat_detection_enabled
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Default Threat",
            enabled=True,
            severity=AlertSeverity.LOW,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Assert: Should default to False
        assert hasattr(rule, "threat_detection_enabled")
        assert rule.threat_detection_enabled is False

    def test_smoke_fire_detection_enabled_defaults_to_false(self) -> None:
        """Test that smoke_fire_detection_enabled defaults to False."""
        # Arrange & Act: Create rule without smoke_fire_detection_enabled
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Default Smoke",
            enabled=True,
            severity=AlertSeverity.LOW,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Assert: Should default to False
        assert hasattr(rule, "smoke_fire_detection_enabled")
        assert rule.smoke_fire_detection_enabled is False

    def test_smoke_fire_consecutive_required_defaults_to_2(self) -> None:
        """Test that smoke_fire_consecutive_required defaults to 2."""
        # Arrange & Act: Create rule without smoke_fire_consecutive_required
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Default Consecutive",
            enabled=True,
            severity=AlertSeverity.LOW,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Assert: Should default to 2
        assert hasattr(rule, "smoke_fire_consecutive_required")
        assert rule.smoke_fire_consecutive_required == 2


# =============================================================================
# Nullable and Type Tests
# =============================================================================


class TestAlertRuleFieldTypes:
    """Tests for field types and nullability of new AlertRule fields."""

    def test_dwell_threshold_seconds_is_nullable_integer(self) -> None:
        """Test that dwell_threshold_seconds is a nullable integer field."""
        # Arrange & Act: Create rule with null dwell_threshold_seconds
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Null Dwell",
            enabled=True,
            severity=AlertSeverity.LOW,
            dwell_threshold_seconds=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Assert: Should accept None
        assert rule.dwell_threshold_seconds is None

    def test_pose_types_is_json_array(self) -> None:
        """Test that pose_types stores as JSON array."""
        # Arrange & Act: Create rule with pose_types array
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="JSON Pose",
            enabled=True,
            severity=AlertSeverity.LOW,
            pose_types=["crouching", "lying_down", "arms_raised"],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Assert: Should store and retrieve as list
        assert isinstance(rule.pose_types, list)
        assert len(rule.pose_types) == 3

    def test_action_types_is_json_array(self) -> None:
        """Test that action_types stores as JSON array."""
        # Arrange & Act: Create rule with action_types array
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="JSON Action",
            enabled=True,
            severity=AlertSeverity.LOW,
            action_types=["loitering", "running", "climbing"],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Assert: Should store and retrieve as list
        assert isinstance(rule.action_types, list)
        assert len(rule.action_types) == 3

    def test_threat_types_is_json_array(self) -> None:
        """Test that threat_types stores as JSON array."""
        # Arrange & Act: Create rule with threat_types array
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="JSON Threat",
            enabled=True,
            severity=AlertSeverity.LOW,
            threat_types=["gun", "knife", "explosive"],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Assert: Should store and retrieve as list
        assert isinstance(rule.threat_types, list)
        assert len(rule.threat_types) == 3

    def test_confidence_thresholds_are_floats(self) -> None:
        """Test that all confidence threshold fields accept float values."""
        # Arrange & Act: Create rule with all confidence thresholds
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Float Confidence",
            enabled=True,
            severity=AlertSeverity.LOW,
            pose_confidence_threshold=0.85,
            action_confidence_threshold=0.80,
            threat_confidence_threshold=0.90,
            smoke_fire_confidence_threshold=0.75,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Assert: Should store as float
        assert isinstance(rule.pose_confidence_threshold, float)
        assert isinstance(rule.action_confidence_threshold, float)
        assert isinstance(rule.threat_confidence_threshold, float)
        assert isinstance(rule.smoke_fire_confidence_threshold, float)


# =============================================================================
# Database Column Tests
# =============================================================================


class TestAlertRuleDatabaseColumns:
    """Tests for database column definitions of new AlertRule fields."""

    def test_new_fields_have_database_columns(self) -> None:
        """Test that new fields are mapped to database columns.

        This test verifies that SQLAlchemy has created column mappings
        for all new fields.
        """
        # Arrange: Get mapper for AlertRule
        mapper = inspect(AlertRule)

        # Act & Assert: Check that new columns exist in mapper
        column_names = [column.key for column in mapper.columns]

        expected_columns = [
            "dwell_threshold_seconds",
            "exclude_household_members",
            "pose_types",
            "pose_confidence_threshold",
            "action_types",
            "action_confidence_threshold",
            "threat_detection_enabled",
            "threat_types",
            "threat_min_severity",
            "threat_confidence_threshold",
            "smoke_fire_detection_enabled",
            "smoke_fire_consecutive_required",
            "smoke_fire_confidence_threshold",
        ]

        for column in expected_columns:
            assert column in column_names, (
                f"Expected column '{column}' not found in AlertRule mapper"
            )

    def test_json_fields_use_correct_type(self) -> None:
        """Test that JSON array fields use JSON or JSONB column type."""
        # Arrange: Get mapper for AlertRule
        mapper = inspect(AlertRule)

        # Act: Get column types for JSON fields
        json_fields = ["pose_types", "action_types", "threat_types"]

        for field_name in json_fields:
            column = mapper.columns[field_name]
            # Assert: Should be JSON or JSONB type
            assert column.type.__class__.__name__ in [
                "JSON",
                "JSONB",
            ], f"Field '{field_name}' should use JSON/JSONB type"

    def test_boolean_fields_have_correct_defaults(self) -> None:
        """Test that boolean fields have correct default values in database."""
        # Arrange: Get mapper for AlertRule
        mapper = inspect(AlertRule)

        # Act & Assert: Check boolean field defaults
        exclude_household = mapper.columns["exclude_household_members"]
        assert exclude_household.default is not None or exclude_household.server_default is not None

        threat_enabled = mapper.columns["threat_detection_enabled"]
        assert threat_enabled.default is not None or threat_enabled.server_default is not None

        smoke_fire_enabled = mapper.columns["smoke_fire_detection_enabled"]
        assert (
            smoke_fire_enabled.default is not None or smoke_fire_enabled.server_default is not None
        )


# =============================================================================
# Integration Tests
# =============================================================================


class TestAlertRuleAllNewFieldsTogether:
    """Tests for using all new fields together in AlertRule."""

    def test_create_rule_with_all_new_fields(self) -> None:
        """Test creating AlertRule with all new condition fields."""
        # Arrange & Act: Create comprehensive rule
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Comprehensive Security Rule",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            # Dwell time conditions
            dwell_threshold_seconds=30,
            exclude_household_members=True,
            # Pose conditions
            pose_types=["crouching", "lying_down"],
            pose_confidence_threshold=0.85,
            # Action conditions
            action_types=["loitering", "peering_through_window"],
            action_confidence_threshold=0.80,
            # Threat conditions
            threat_detection_enabled=True,
            threat_types=["gun", "knife"],
            threat_min_severity="high",
            threat_confidence_threshold=0.90,
            # Smoke/fire conditions
            smoke_fire_detection_enabled=True,
            smoke_fire_consecutive_required=2,
            smoke_fire_confidence_threshold=0.85,
            # Standard fields
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Assert: All fields should be set correctly
        assert rule.dwell_threshold_seconds == 30
        assert rule.exclude_household_members is True
        assert rule.pose_types == ["crouching", "lying_down"]
        assert rule.pose_confidence_threshold == 0.85
        assert rule.action_types == ["loitering", "peering_through_window"]
        assert rule.action_confidence_threshold == 0.80
        assert rule.threat_detection_enabled is True
        assert rule.threat_types == ["gun", "knife"]
        assert rule.threat_min_severity == "high"
        assert rule.threat_confidence_threshold == 0.90
        assert rule.smoke_fire_detection_enabled is True
        assert rule.smoke_fire_consecutive_required == 2
        assert rule.smoke_fire_confidence_threshold == 0.85

    def test_repr_includes_new_fields(self) -> None:
        """Test that AlertRule __repr__ can handle new fields.

        Note: This test ensures __repr__ doesn't crash with new fields,
        but doesn't require them to be included in the output.
        """
        # Arrange & Act: Create rule with new fields
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Test Rule",
            enabled=True,
            severity=AlertSeverity.HIGH,
            dwell_threshold_seconds=30,
            pose_types=["crouching"],
            threat_detection_enabled=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Act: Call __repr__
        repr_str = repr(rule)

        # Assert: Should not crash and should return a string
        assert isinstance(repr_str, str)
        assert "AlertRule" in repr_str
        assert "Test Rule" in repr_str
