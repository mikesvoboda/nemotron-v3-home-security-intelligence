"""Unit tests for new Alert Rule Condition Types schema validation (TDD RED phase).

This module contains failing tests that define expected schema validation for:
1. dwell_time condition fields
2. pose_type condition fields
3. action_type condition fields
4. threat_detected condition fields
5. smoke_fire condition fields

These tests are written FIRST (TDD red phase) and will initially fail.
Implementation should follow in backend/api/schemas/alerts.py.

Design reference: docs/plans/2026-02-01-platform-enhancement-strategy-design.md
Related issue: NEM-5084
"""

import pytest
from pydantic import ValidationError

from backend.api.schemas.alerts import (
    AlertRuleCreate,
    AlertRuleUpdate,
    AlertSeverity,
)

# =============================================================================
# Dwell Time Schema Tests
# =============================================================================


class TestDwellTimeSchemaValidation:
    """Tests for dwell_time condition schema validation."""

    def test_dwell_time_schema_validation_valid(self) -> None:
        """Test that valid dwell_time fields pass validation.

        Expected fields:
        - dwell_threshold_seconds: int >= 0
        - exclude_household_members: bool (optional, default False)
        """
        # Arrange & Act: Create rule with dwell_time condition
        rule = AlertRuleCreate(
            name="Loitering Alert",
            severity=AlertSeverity.MEDIUM,
            dwell_threshold_seconds=30,  # NEW FIELD - will fail until implemented
            exclude_household_members=False,  # NEW FIELD
        )

        # Assert: Should be valid
        assert rule.dwell_threshold_seconds == 30
        assert rule.exclude_household_members is False

    def test_dwell_time_threshold_must_be_positive(self) -> None:
        """Test that dwell_threshold_seconds must be >= 0."""
        # Act & Assert: Negative threshold should raise validation error
        with pytest.raises(ValidationError) as exc_info:
            AlertRuleCreate(
                name="Invalid Loitering",
                severity=AlertSeverity.MEDIUM,
                dwell_threshold_seconds=-10,  # Invalid
            )

        errors = exc_info.value.errors()
        assert any(
            "dwell_threshold_seconds" in str(error["loc"])
            and "greater than or equal to 0" in str(error["msg"])
            for error in errors
        )

    def test_dwell_time_threshold_optional(self) -> None:
        """Test that dwell_threshold_seconds is optional (null = no dwell condition)."""
        # Arrange & Act: Create rule without dwell_time
        rule = AlertRuleCreate(
            name="No Dwell Condition",
            severity=AlertSeverity.LOW,
        )

        # Assert: Should be valid with null dwell_threshold_seconds
        assert rule.dwell_threshold_seconds is None

    def test_dwell_time_exclude_household_defaults_false(self) -> None:
        """Test that exclude_household_members defaults to False."""
        # Arrange & Act: Create rule without specifying exclude_household_members
        rule = AlertRuleCreate(
            name="Loitering Alert",
            severity=AlertSeverity.MEDIUM,
            dwell_threshold_seconds=30,
        )

        # Assert: Should default to False
        assert hasattr(rule, "exclude_household_members")
        assert rule.exclude_household_members is False

    def test_dwell_time_update_schema(self) -> None:
        """Test that dwell_time fields work in update schema."""
        # Arrange & Act: Create update with dwell_time fields
        update = AlertRuleUpdate(
            dwell_threshold_seconds=60,  # NEW FIELD
            exclude_household_members=True,  # NEW FIELD
        )

        # Assert: Should be valid
        assert update.dwell_threshold_seconds == 60
        assert update.exclude_household_members is True


# =============================================================================
# Pose Type Schema Tests
# =============================================================================


class TestPoseTypeSchemaValidation:
    """Tests for pose_type condition schema validation."""

    def test_pose_type_schema_validation_valid(self) -> None:
        """Test that valid pose_types field passes validation.

        Expected fields:
        - pose_types: list[str] (valid: standing, crouching, bending_over, arms_raised, sitting, lying_down)
        - pose_confidence_threshold: float 0.0-1.0 (optional)
        """
        # Arrange & Act: Create rule with pose_types condition
        rule = AlertRuleCreate(
            name="Suspicious Pose Alert",
            severity=AlertSeverity.HIGH,
            pose_types=["crouching", "lying_down"],  # NEW FIELD - will fail until implemented
            pose_confidence_threshold=0.85,  # NEW FIELD
        )

        # Assert: Should be valid
        assert rule.pose_types == ["crouching", "lying_down"]
        assert rule.pose_confidence_threshold == 0.85

    def test_pose_type_validates_allowed_values(self) -> None:
        """Test that pose_types validates against allowed pose classes.

        Allowed poses: standing, crouching, bending_over, arms_raised, sitting, lying_down, unknown
        """
        # Act & Assert: Invalid pose type should raise validation error
        with pytest.raises(ValidationError) as exc_info:
            AlertRuleCreate(
                name="Invalid Pose",
                severity=AlertSeverity.MEDIUM,
                pose_types=["flying", "teleporting"],  # Invalid poses
            )

        errors = exc_info.value.errors()
        assert any("pose_types" in str(error["loc"]) for error in errors)

    def test_pose_type_confidence_range_validation(self) -> None:
        """Test that pose_confidence_threshold must be between 0.0 and 1.0."""
        # Act & Assert: Out of range confidence should raise validation error
        with pytest.raises(ValidationError) as exc_info:
            AlertRuleCreate(
                name="Invalid Confidence",
                severity=AlertSeverity.MEDIUM,
                pose_types=["crouching"],
                pose_confidence_threshold=1.5,  # Invalid (> 1.0)
            )

        errors = exc_info.value.errors()
        assert any(
            "pose_confidence_threshold" in str(error["loc"])
            and "less than or equal to 1" in str(error["msg"])
            for error in errors
        )

    def test_pose_type_empty_list_valid(self) -> None:
        """Test that empty pose_types list is valid (no pose filtering)."""
        # Arrange & Act: Create rule with empty pose_types
        rule = AlertRuleCreate(
            name="No Pose Filter",
            severity=AlertSeverity.LOW,
            pose_types=[],
        )

        # Assert: Should be valid
        assert rule.pose_types == []

    def test_pose_type_optional(self) -> None:
        """Test that pose_types is optional (null = no pose condition)."""
        # Arrange & Act: Create rule without pose_types
        rule = AlertRuleCreate(
            name="No Pose Condition",
            severity=AlertSeverity.LOW,
        )

        # Assert: Should be valid with null pose_types
        assert rule.pose_types is None

    def test_pose_type_update_schema(self) -> None:
        """Test that pose_types fields work in update schema."""
        # Arrange & Act: Create update with pose fields
        update = AlertRuleUpdate(
            pose_types=["lying_down"],  # NEW FIELD
            pose_confidence_threshold=0.9,  # NEW FIELD
        )

        # Assert: Should be valid
        assert update.pose_types == ["lying_down"]
        assert update.pose_confidence_threshold == 0.9


# =============================================================================
# Action Type Schema Tests
# =============================================================================


class TestActionTypeSchemaValidation:
    """Tests for action_type condition schema validation."""

    def test_action_type_schema_validation_valid(self) -> None:
        """Test that valid action_types field passes validation.

        Expected fields:
        - action_types: list[str] (X-CLIP recognized actions)
        - action_confidence_threshold: float 0.0-1.0 (optional)
        """
        # Arrange & Act: Create rule with action_types condition
        rule = AlertRuleCreate(
            name="Suspicious Action Alert",
            severity=AlertSeverity.HIGH,
            action_types=[
                "loitering",
                "peering_through_window",
            ],  # NEW FIELD - will fail until implemented
            action_confidence_threshold=0.80,  # NEW FIELD
        )

        # Assert: Should be valid
        assert rule.action_types == ["loitering", "peering_through_window"]
        assert rule.action_confidence_threshold == 0.80

    def test_action_type_confidence_range_validation(self) -> None:
        """Test that action_confidence_threshold must be between 0.0 and 1.0."""
        # Act & Assert: Out of range confidence should raise validation error
        with pytest.raises(ValidationError) as exc_info:
            AlertRuleCreate(
                name="Invalid Confidence",
                severity=AlertSeverity.MEDIUM,
                action_types=["loitering"],
                action_confidence_threshold=-0.1,  # Invalid (< 0.0)
            )

        errors = exc_info.value.errors()
        assert any("action_confidence_threshold" in str(error["loc"]) for error in errors)

    def test_action_type_empty_list_valid(self) -> None:
        """Test that empty action_types list is valid (no action filtering)."""
        # Arrange & Act: Create rule with empty action_types
        rule = AlertRuleCreate(
            name="No Action Filter",
            severity=AlertSeverity.LOW,
            action_types=[],
        )

        # Assert: Should be valid
        assert rule.action_types == []

    def test_action_type_optional(self) -> None:
        """Test that action_types is optional (null = no action condition)."""
        # Arrange & Act: Create rule without action_types
        rule = AlertRuleCreate(
            name="No Action Condition",
            severity=AlertSeverity.LOW,
        )

        # Assert: Should be valid with null action_types
        assert rule.action_types is None

    def test_action_type_allows_any_string(self) -> None:
        """Test that action_types allows any string (X-CLIP is extensible).

        Note: Unlike pose_types, action_types doesn't validate specific values
        since X-CLIP can recognize many actions and the list may grow.
        """
        # Arrange & Act: Create rule with various action names
        rule = AlertRuleCreate(
            name="Custom Actions",
            severity=AlertSeverity.MEDIUM,
            action_types=["custom_action_1", "custom_action_2"],
        )

        # Assert: Should be valid (no enum restriction)
        assert rule.action_types == ["custom_action_1", "custom_action_2"]

    def test_action_type_update_schema(self) -> None:
        """Test that action_types fields work in update schema."""
        # Arrange & Act: Create update with action fields
        update = AlertRuleUpdate(
            action_types=["running", "jumping"],  # NEW FIELD
            action_confidence_threshold=0.85,  # NEW FIELD
        )

        # Assert: Should be valid
        assert update.action_types == ["running", "jumping"]
        assert update.action_confidence_threshold == 0.85


# =============================================================================
# Threat Detection Schema Tests
# =============================================================================


class TestThreatDetectedSchemaValidation:
    """Tests for threat_detected condition schema validation."""

    def test_threat_detected_schema_validation_valid(self) -> None:
        """Test that valid threat detection fields pass validation.

        Expected fields:
        - threat_detection_enabled: bool
        - threat_types: list[str] (optional, filter by type: gun, knife, etc.)
        - threat_min_severity: str (optional: critical, high, medium, low)
        - threat_confidence_threshold: float 0.0-1.0 (optional)
        """
        # Arrange & Act: Create rule with threat detection
        rule = AlertRuleCreate(
            name="Weapon Detection",
            severity=AlertSeverity.CRITICAL,
            threat_detection_enabled=True,  # NEW FIELD - will fail until implemented
            threat_types=["gun", "knife"],  # NEW FIELD
            threat_min_severity="high",  # NEW FIELD
            threat_confidence_threshold=0.90,  # NEW FIELD
        )

        # Assert: Should be valid
        assert rule.threat_detection_enabled is True
        assert rule.threat_types == ["gun", "knife"]
        assert rule.threat_min_severity == "high"
        assert rule.threat_confidence_threshold == 0.90

    def test_threat_detection_enabled_defaults_false(self) -> None:
        """Test that threat_detection_enabled defaults to False."""
        # Arrange & Act: Create rule without threat_detection_enabled
        rule = AlertRuleCreate(
            name="Normal Alert",
            severity=AlertSeverity.LOW,
        )

        # Assert: Should default to False
        assert hasattr(rule, "threat_detection_enabled")
        assert rule.threat_detection_enabled is False

    def test_threat_types_validates_allowed_values(self) -> None:
        """Test that threat_types validates against allowed threat types.

        Allowed: gun, knife, grenade, explosive, weapon, other
        """
        # Arrange & Act: Valid threat types should pass
        rule = AlertRuleCreate(
            name="Valid Threats",
            severity=AlertSeverity.CRITICAL,
            threat_detection_enabled=True,
            threat_types=["gun", "knife", "explosive"],
        )

        # Assert: Should be valid
        assert rule.threat_types == ["gun", "knife", "explosive"]

    def test_threat_min_severity_validates_allowed_values(self) -> None:
        """Test that threat_min_severity validates against allowed severities.

        Allowed: critical, high, medium, low
        """
        # Act & Assert: Invalid severity should raise validation error
        with pytest.raises(ValidationError) as exc_info:
            AlertRuleCreate(
                name="Invalid Severity",
                severity=AlertSeverity.CRITICAL,
                threat_detection_enabled=True,
                threat_min_severity="ultra_critical",  # Invalid
            )

        errors = exc_info.value.errors()
        assert any("threat_min_severity" in str(error["loc"]) for error in errors)

    def test_threat_confidence_range_validation(self) -> None:
        """Test that threat_confidence_threshold must be between 0.0 and 1.0."""
        # Act & Assert: Out of range confidence should raise validation error
        with pytest.raises(ValidationError) as exc_info:
            AlertRuleCreate(
                name="Invalid Confidence",
                severity=AlertSeverity.CRITICAL,
                threat_detection_enabled=True,
                threat_confidence_threshold=2.0,  # Invalid (> 1.0)
            )

        errors = exc_info.value.errors()
        assert any("threat_confidence_threshold" in str(error["loc"]) for error in errors)

    def test_threat_fields_optional(self) -> None:
        """Test that threat fields are optional when threat_detection_enabled=False."""
        # Arrange & Act: Create rule without threat fields
        rule = AlertRuleCreate(
            name="No Threats",
            severity=AlertSeverity.LOW,
            threat_detection_enabled=False,
        )

        # Assert: Should be valid
        assert rule.threat_detection_enabled is False
        assert rule.threat_types is None or rule.threat_types == []

    def test_threat_detection_update_schema(self) -> None:
        """Test that threat detection fields work in update schema."""
        # Arrange & Act: Create update with threat fields
        update = AlertRuleUpdate(
            threat_detection_enabled=True,  # NEW FIELD
            threat_types=["gun"],  # NEW FIELD
            threat_min_severity="critical",  # NEW FIELD
            threat_confidence_threshold=0.95,  # NEW FIELD
        )

        # Assert: Should be valid
        assert update.threat_detection_enabled is True
        assert update.threat_types == ["gun"]
        assert update.threat_min_severity == "critical"
        assert update.threat_confidence_threshold == 0.95


# =============================================================================
# Smoke/Fire Detection Schema Tests
# =============================================================================


class TestSmokeFireSchemaValidation:
    """Tests for smoke_fire condition schema validation."""

    def test_smoke_fire_schema_validation_valid(self) -> None:
        """Test that valid smoke_fire fields pass validation.

        Expected fields:
        - smoke_fire_detection_enabled: bool
        - smoke_fire_consecutive_required: int >= 1 (default 2)
        - smoke_fire_confidence_threshold: float 0.0-1.0 (optional)
        """
        # Arrange & Act: Create rule with smoke/fire detection
        rule = AlertRuleCreate(
            name="Fire Safety Alert",
            severity=AlertSeverity.CRITICAL,
            smoke_fire_detection_enabled=True,  # NEW FIELD - will fail until implemented
            smoke_fire_consecutive_required=2,  # NEW FIELD
            smoke_fire_confidence_threshold=0.85,  # NEW FIELD
        )

        # Assert: Should be valid
        assert rule.smoke_fire_detection_enabled is True
        assert rule.smoke_fire_consecutive_required == 2
        assert rule.smoke_fire_confidence_threshold == 0.85

    def test_smoke_fire_enabled_defaults_false(self) -> None:
        """Test that smoke_fire_detection_enabled defaults to False."""
        # Arrange & Act: Create rule without smoke_fire_detection_enabled
        rule = AlertRuleCreate(
            name="Normal Alert",
            severity=AlertSeverity.LOW,
        )

        # Assert: Should default to False
        assert hasattr(rule, "smoke_fire_detection_enabled")
        assert rule.smoke_fire_detection_enabled is False

    def test_smoke_fire_consecutive_must_be_positive(self) -> None:
        """Test that smoke_fire_consecutive_required must be >= 1."""
        # Act & Assert: Zero or negative consecutive should raise validation error
        with pytest.raises(ValidationError) as exc_info:
            AlertRuleCreate(
                name="Invalid Consecutive",
                severity=AlertSeverity.CRITICAL,
                smoke_fire_detection_enabled=True,
                smoke_fire_consecutive_required=0,  # Invalid
            )

        errors = exc_info.value.errors()
        assert any(
            "smoke_fire_consecutive_required" in str(error["loc"])
            and "greater than or equal to 1" in str(error["msg"])
            for error in errors
        )

    def test_smoke_fire_consecutive_defaults_to_2(self) -> None:
        """Test that smoke_fire_consecutive_required defaults to 2.

        This reduces false positives by requiring confirmation.
        """
        # Arrange & Act: Create rule without specifying consecutive
        rule = AlertRuleCreate(
            name="Fire Alert",
            severity=AlertSeverity.CRITICAL,
            smoke_fire_detection_enabled=True,
        )

        # Assert: Should default to 2
        assert hasattr(rule, "smoke_fire_consecutive_required")
        assert rule.smoke_fire_consecutive_required == 2

    def test_smoke_fire_confidence_range_validation(self) -> None:
        """Test that smoke_fire_confidence_threshold must be between 0.0 and 1.0."""
        # Act & Assert: Out of range confidence should raise validation error
        with pytest.raises(ValidationError) as exc_info:
            AlertRuleCreate(
                name="Invalid Confidence",
                severity=AlertSeverity.CRITICAL,
                smoke_fire_detection_enabled=True,
                smoke_fire_confidence_threshold=1.2,  # Invalid (> 1.0)
            )

        errors = exc_info.value.errors()
        assert any("smoke_fire_confidence_threshold" in str(error["loc"]) for error in errors)

    def test_smoke_fire_update_schema(self) -> None:
        """Test that smoke_fire fields work in update schema."""
        # Arrange & Act: Create update with smoke_fire fields
        update = AlertRuleUpdate(
            smoke_fire_detection_enabled=True,  # NEW FIELD
            smoke_fire_consecutive_required=3,  # NEW FIELD
            smoke_fire_confidence_threshold=0.90,  # NEW FIELD
        )

        # Assert: Should be valid
        assert update.smoke_fire_detection_enabled is True
        assert update.smoke_fire_consecutive_required == 3
        assert update.smoke_fire_confidence_threshold == 0.90


# =============================================================================
# Combined Schema Tests
# =============================================================================


class TestCombinedSchemaValidation:
    """Tests for combining multiple new condition types in schemas."""

    def test_all_new_conditions_in_single_rule(self) -> None:
        """Test that all new condition types can be combined in one rule."""
        # Arrange & Act: Create rule with all new condition types
        rule = AlertRuleCreate(
            name="Comprehensive Security Rule",
            severity=AlertSeverity.HIGH,
            dwell_threshold_seconds=30,  # NEW
            pose_types=["crouching"],  # NEW
            action_types=["loitering"],  # NEW
            threat_detection_enabled=True,  # NEW
            smoke_fire_detection_enabled=False,  # NEW
        )

        # Assert: Should be valid
        assert rule.dwell_threshold_seconds == 30
        assert rule.pose_types == ["crouching"]
        assert rule.action_types == ["loitering"]
        assert rule.threat_detection_enabled is True
        assert rule.smoke_fire_detection_enabled is False

    def test_new_conditions_with_existing_conditions(self) -> None:
        """Test that new conditions work alongside existing conditions."""
        # Arrange & Act: Create rule with mixed old and new conditions
        rule = AlertRuleCreate(
            name="Mixed Conditions",
            severity=AlertSeverity.HIGH,
            risk_threshold=70,  # Existing
            camera_ids=["front_door"],  # Existing
            min_confidence=0.8,  # Existing
            dwell_threshold_seconds=30,  # NEW
            threat_detection_enabled=True,  # NEW
        )

        # Assert: Should be valid
        assert rule.risk_threshold == 70
        assert rule.camera_ids == ["front_door"]
        assert rule.min_confidence == 0.8
        assert rule.dwell_threshold_seconds == 30
        assert rule.threat_detection_enabled is True

    def test_partial_update_with_new_conditions(self) -> None:
        """Test that partial updates work with new condition fields."""
        # Arrange & Act: Create update with only some new fields
        update = AlertRuleUpdate(
            dwell_threshold_seconds=60,  # NEW
            # Other fields not specified (partial update)
        )

        # Assert: Should be valid
        assert update.dwell_threshold_seconds == 60
        assert update.pose_types is None  # Not updated
        assert update.action_types is None  # Not updated
