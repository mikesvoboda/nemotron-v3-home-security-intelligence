"""Unit tests for CHECK constraints on models.

Tests verify that CHECK constraints are properly defined in model __table_args__.
These tests do not require a database connection - they validate the SQLAlchemy
model definitions themselves.

Related Linear issues:
- NEM-1492: Add CHECK constraints for enum-like string columns
- NEM-1496: Add database-level constraints for business rules
"""

import pytest

from backend.models.alert import AlertRule
from backend.models.audit import AuditLog
from backend.models.baseline import ActivityBaseline, ClassBaseline
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.models.event_audit import EventAudit
from backend.models.log import Log
from backend.models.scene_change import SceneChange
from backend.models.zone import Zone

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


def _get_check_constraint_names(model_class):
    """Extract CHECK constraint names from a model's __table_args__."""
    table_args = getattr(model_class, "__table_args__", ())
    constraint_names = set()

    # __table_args__ can be a tuple or dict
    if isinstance(table_args, dict):
        return constraint_names

    for arg in table_args:
        # Check if it's a CheckConstraint by looking for the name attribute
        if hasattr(arg, "name") and hasattr(arg, "_create_rule"):
            constraint_names.add(arg.name)

    return constraint_names


def _get_check_constraint_by_name(model_class, constraint_name):
    """Get a CHECK constraint by name from a model."""
    table_args = getattr(model_class, "__table_args__", ())

    if isinstance(table_args, dict):
        return None

    for arg in table_args:
        if hasattr(arg, "name") and arg.name == constraint_name:
            return arg

    return None


# =============================================================================
# NEM-1492: CHECK constraints for enum-like string columns
# =============================================================================


class TestCameraStatusConstraint:
    """Tests for Camera.status CHECK constraint."""

    def test_camera_has_status_check_constraint(self):
        """Test that Camera model has a CHECK constraint for status."""
        constraint_names = _get_check_constraint_names(Camera)
        assert "ck_cameras_status" in constraint_names

    def test_camera_status_constraint_expression(self):
        """Test that Camera status constraint has correct expression."""
        constraint = _get_check_constraint_by_name(Camera, "ck_cameras_status")
        assert constraint is not None
        # Check that the constraint text includes the valid values
        constraint_text = str(constraint.sqltext)
        assert "online" in constraint_text
        assert "offline" in constraint_text
        assert "error" in constraint_text
        assert "unknown" in constraint_text


class TestEventRiskLevelConstraint:
    """Tests for Event.risk_level CHECK constraint."""

    def test_event_has_risk_level_check_constraint(self):
        """Test that Event model has a CHECK constraint for risk_level."""
        constraint_names = _get_check_constraint_names(Event)
        assert "ck_events_risk_level" in constraint_names

    def test_event_risk_level_constraint_expression(self):
        """Test that Event risk_level constraint has correct expression."""
        constraint = _get_check_constraint_by_name(Event, "ck_events_risk_level")
        assert constraint is not None
        constraint_text = str(constraint.sqltext)
        # Should allow NULL or one of the valid values
        assert "NULL" in constraint_text
        assert "low" in constraint_text
        assert "medium" in constraint_text
        assert "high" in constraint_text
        assert "critical" in constraint_text


class TestDetectionMediaTypeConstraint:
    """Tests for Detection.media_type CHECK constraint."""

    def test_detection_has_media_type_check_constraint(self):
        """Test that Detection model has a CHECK constraint for media_type."""
        constraint_names = _get_check_constraint_names(Detection)
        assert "ck_detections_media_type" in constraint_names

    def test_detection_media_type_constraint_expression(self):
        """Test that Detection media_type constraint has correct expression."""
        constraint = _get_check_constraint_by_name(Detection, "ck_detections_media_type")
        assert constraint is not None
        constraint_text = str(constraint.sqltext)
        assert "NULL" in constraint_text
        assert "image" in constraint_text
        assert "video" in constraint_text


class TestLogLevelConstraint:
    """Tests for Log.level CHECK constraint."""

    def test_log_has_level_check_constraint(self):
        """Test that Log model has a CHECK constraint for level."""
        constraint_names = _get_check_constraint_names(Log)
        assert "ck_logs_level" in constraint_names

    def test_log_level_constraint_expression(self):
        """Test that Log level constraint has correct expression."""
        constraint = _get_check_constraint_by_name(Log, "ck_logs_level")
        assert constraint is not None
        constraint_text = str(constraint.sqltext)
        assert "DEBUG" in constraint_text
        assert "INFO" in constraint_text
        assert "WARNING" in constraint_text
        assert "ERROR" in constraint_text
        assert "CRITICAL" in constraint_text


class TestLogSourceConstraint:
    """Tests for Log.source CHECK constraint."""

    def test_log_has_source_check_constraint(self):
        """Test that Log model has a CHECK constraint for source."""
        constraint_names = _get_check_constraint_names(Log)
        assert "ck_logs_source" in constraint_names

    def test_log_source_constraint_expression(self):
        """Test that Log source constraint has correct expression."""
        constraint = _get_check_constraint_by_name(Log, "ck_logs_source")
        assert constraint is not None
        constraint_text = str(constraint.sqltext)
        assert "backend" in constraint_text
        assert "frontend" in constraint_text


class TestAuditLogStatusConstraint:
    """Tests for AuditLog.status CHECK constraint."""

    def test_audit_log_has_status_check_constraint(self):
        """Test that AuditLog model has a CHECK constraint for status."""
        constraint_names = _get_check_constraint_names(AuditLog)
        assert "ck_audit_logs_status" in constraint_names

    def test_audit_log_status_constraint_expression(self):
        """Test that AuditLog status constraint has correct expression."""
        constraint = _get_check_constraint_by_name(AuditLog, "ck_audit_logs_status")
        assert constraint is not None
        constraint_text = str(constraint.sqltext)
        assert "success" in constraint_text
        assert "failure" in constraint_text


# =============================================================================
# NEM-1496: CHECK constraints for business rules
# =============================================================================


class TestEventRiskScoreConstraint:
    """Tests for Event.risk_score CHECK constraint."""

    def test_event_has_risk_score_check_constraint(self):
        """Test that Event model has a CHECK constraint for risk_score range."""
        constraint_names = _get_check_constraint_names(Event)
        assert "ck_events_risk_score_range" in constraint_names

    def test_event_risk_score_constraint_expression(self):
        """Test that Event risk_score constraint enforces 0-100 range."""
        constraint = _get_check_constraint_by_name(Event, "ck_events_risk_score_range")
        assert constraint is not None
        constraint_text = str(constraint.sqltext)
        assert "NULL" in constraint_text
        assert "0" in constraint_text
        assert "100" in constraint_text


class TestEventTimeOrderConstraint:
    """Tests for Event time order CHECK constraint."""

    def test_event_has_time_order_check_constraint(self):
        """Test that Event model has a CHECK constraint for time ordering."""
        constraint_names = _get_check_constraint_names(Event)
        assert "ck_events_time_order" in constraint_names

    def test_event_time_order_constraint_expression(self):
        """Test that Event time_order constraint enforces ended_at >= started_at."""
        constraint = _get_check_constraint_by_name(Event, "ck_events_time_order")
        assert constraint is not None
        constraint_text = str(constraint.sqltext)
        assert "ended_at" in constraint_text
        assert "started_at" in constraint_text


class TestDetectionConfidenceConstraint:
    """Tests for Detection.confidence CHECK constraint."""

    def test_detection_has_confidence_check_constraint(self):
        """Test that Detection model has a CHECK constraint for confidence range."""
        constraint_names = _get_check_constraint_names(Detection)
        assert "ck_detections_confidence_range" in constraint_names

    def test_detection_confidence_constraint_expression(self):
        """Test that Detection confidence constraint enforces 0.0-1.0 range."""
        constraint = _get_check_constraint_by_name(Detection, "ck_detections_confidence_range")
        assert constraint is not None
        constraint_text = str(constraint.sqltext)
        assert "NULL" in constraint_text
        assert "0.0" in constraint_text
        assert "1.0" in constraint_text


class TestActivityBaselineHourConstraint:
    """Tests for ActivityBaseline.hour CHECK constraint."""

    def test_activity_baseline_has_hour_check_constraint(self):
        """Test that ActivityBaseline has a CHECK constraint for hour range."""
        constraint_names = _get_check_constraint_names(ActivityBaseline)
        assert "ck_activity_baselines_hour_range" in constraint_names

    def test_activity_baseline_hour_constraint_expression(self):
        """Test that ActivityBaseline hour constraint enforces 0-23 range."""
        constraint = _get_check_constraint_by_name(
            ActivityBaseline, "ck_activity_baselines_hour_range"
        )
        assert constraint is not None
        constraint_text = str(constraint.sqltext)
        assert "hour" in constraint_text
        assert "0" in constraint_text
        assert "23" in constraint_text


class TestActivityBaselineDowConstraint:
    """Tests for ActivityBaseline.day_of_week CHECK constraint."""

    def test_activity_baseline_has_dow_check_constraint(self):
        """Test that ActivityBaseline has a CHECK constraint for day_of_week range."""
        constraint_names = _get_check_constraint_names(ActivityBaseline)
        assert "ck_activity_baselines_dow_range" in constraint_names

    def test_activity_baseline_dow_constraint_expression(self):
        """Test that ActivityBaseline day_of_week constraint enforces 0-6 range."""
        constraint = _get_check_constraint_by_name(
            ActivityBaseline, "ck_activity_baselines_dow_range"
        )
        assert constraint is not None
        constraint_text = str(constraint.sqltext)
        assert "day_of_week" in constraint_text
        assert "0" in constraint_text
        assert "6" in constraint_text


class TestClassBaselineHourConstraint:
    """Tests for ClassBaseline.hour CHECK constraint."""

    def test_class_baseline_has_hour_check_constraint(self):
        """Test that ClassBaseline has a CHECK constraint for hour range."""
        constraint_names = _get_check_constraint_names(ClassBaseline)
        assert "ck_class_baselines_hour_range" in constraint_names

    def test_class_baseline_hour_constraint_expression(self):
        """Test that ClassBaseline hour constraint enforces 0-23 range."""
        constraint = _get_check_constraint_by_name(ClassBaseline, "ck_class_baselines_hour_range")
        assert constraint is not None
        constraint_text = str(constraint.sqltext)
        assert "hour" in constraint_text
        assert "0" in constraint_text
        assert "23" in constraint_text


class TestZonePriorityConstraint:
    """Tests for Zone.priority CHECK constraint."""

    def test_zone_has_priority_check_constraint(self):
        """Test that Zone has a CHECK constraint for non-negative priority."""
        constraint_names = _get_check_constraint_names(Zone)
        assert "ck_zones_priority_non_negative" in constraint_names

    def test_zone_priority_constraint_expression(self):
        """Test that Zone priority constraint enforces non-negative values."""
        constraint = _get_check_constraint_by_name(Zone, "ck_zones_priority_non_negative")
        assert constraint is not None
        constraint_text = str(constraint.sqltext)
        assert "priority" in constraint_text
        assert "0" in constraint_text


class TestZoneColorConstraint:
    """Tests for Zone.color CHECK constraint."""

    def test_zone_has_color_check_constraint(self):
        """Test that Zone has a CHECK constraint for hex color format."""
        constraint_names = _get_check_constraint_names(Zone)
        assert "ck_zones_color_hex" in constraint_names

    def test_zone_color_constraint_expression(self):
        """Test that Zone color constraint enforces hex format."""
        constraint = _get_check_constraint_by_name(Zone, "ck_zones_color_hex")
        assert constraint is not None
        constraint_text = str(constraint.sqltext)
        assert "color" in constraint_text
        # Should contain regex pattern for hex color
        assert "#" in constraint_text or "hex" in constraint_text.lower()


class TestSceneChangeSimilarityConstraint:
    """Tests for SceneChange.similarity_score CHECK constraint."""

    def test_scene_change_has_similarity_check_constraint(self):
        """Test that SceneChange has a CHECK constraint for similarity_score range."""
        constraint_names = _get_check_constraint_names(SceneChange)
        assert "ck_scene_changes_similarity_range" in constraint_names

    def test_scene_change_similarity_constraint_expression(self):
        """Test that SceneChange similarity_score constraint enforces 0.0-1.0 range."""
        constraint = _get_check_constraint_by_name(SceneChange, "ck_scene_changes_similarity_range")
        assert constraint is not None
        constraint_text = str(constraint.sqltext)
        assert "similarity_score" in constraint_text
        assert "0.0" in constraint_text
        assert "1.0" in constraint_text


class TestEventAuditScoreConstraints:
    """Tests for EventAudit quality score CHECK constraints."""

    def test_event_audit_has_all_score_constraints(self):
        """Test that EventAudit has CHECK constraints for all quality scores."""
        constraint_names = _get_check_constraint_names(EventAudit)
        expected_constraints = {
            "ck_event_audits_context_score_range",
            "ck_event_audits_reasoning_score_range",
            "ck_event_audits_risk_justification_range",
            "ck_event_audits_consistency_score_range",
            "ck_event_audits_overall_score_range",
            "ck_event_audits_enrichment_range",
        }
        for constraint_name in expected_constraints:
            assert constraint_name in constraint_names, f"Missing constraint: {constraint_name}"

    def test_event_audit_score_constraints_enforce_1_to_5_range(self):
        """Test that EventAudit score constraints enforce 1.0-5.0 range."""
        score_constraints = [
            "ck_event_audits_context_score_range",
            "ck_event_audits_reasoning_score_range",
            "ck_event_audits_risk_justification_range",
            "ck_event_audits_consistency_score_range",
            "ck_event_audits_overall_score_range",
        ]
        for constraint_name in score_constraints:
            constraint = _get_check_constraint_by_name(EventAudit, constraint_name)
            assert constraint is not None, f"Constraint not found: {constraint_name}"
            constraint_text = str(constraint.sqltext)
            assert "1.0" in constraint_text, f"{constraint_name} missing lower bound"
            assert "5.0" in constraint_text, f"{constraint_name} missing upper bound"

    def test_event_audit_enrichment_constraint_enforces_0_to_1_range(self):
        """Test that EventAudit enrichment_utilization constraint enforces 0.0-1.0 range."""
        constraint = _get_check_constraint_by_name(EventAudit, "ck_event_audits_enrichment_range")
        assert constraint is not None
        constraint_text = str(constraint.sqltext)
        assert "enrichment_utilization" in constraint_text
        assert "0.0" in constraint_text
        assert "1.0" in constraint_text


class TestAlertRuleConstraints:
    """Tests for AlertRule CHECK constraints."""

    def test_alert_rule_has_risk_threshold_constraint(self):
        """Test that AlertRule has a CHECK constraint for risk_threshold range."""
        constraint_names = _get_check_constraint_names(AlertRule)
        assert "ck_alert_rules_risk_threshold_range" in constraint_names

    def test_alert_rule_risk_threshold_constraint_expression(self):
        """Test that AlertRule risk_threshold constraint enforces 0-100 range."""
        constraint = _get_check_constraint_by_name(AlertRule, "ck_alert_rules_risk_threshold_range")
        assert constraint is not None
        constraint_text = str(constraint.sqltext)
        assert "NULL" in constraint_text
        assert "0" in constraint_text
        assert "100" in constraint_text

    def test_alert_rule_has_min_confidence_constraint(self):
        """Test that AlertRule has a CHECK constraint for min_confidence range."""
        constraint_names = _get_check_constraint_names(AlertRule)
        assert "ck_alert_rules_min_confidence_range" in constraint_names

    def test_alert_rule_min_confidence_constraint_expression(self):
        """Test that AlertRule min_confidence constraint enforces 0.0-1.0 range."""
        constraint = _get_check_constraint_by_name(AlertRule, "ck_alert_rules_min_confidence_range")
        assert constraint is not None
        constraint_text = str(constraint.sqltext)
        assert "NULL" in constraint_text
        assert "0.0" in constraint_text
        assert "1.0" in constraint_text

    def test_alert_rule_has_cooldown_constraint(self):
        """Test that AlertRule has a CHECK constraint for cooldown_seconds."""
        constraint_names = _get_check_constraint_names(AlertRule)
        assert "ck_alert_rules_cooldown_non_negative" in constraint_names

    def test_alert_rule_cooldown_constraint_expression(self):
        """Test that AlertRule cooldown_seconds constraint enforces non-negative values."""
        constraint = _get_check_constraint_by_name(
            AlertRule, "ck_alert_rules_cooldown_non_negative"
        )
        assert constraint is not None
        constraint_text = str(constraint.sqltext)
        assert "cooldown_seconds" in constraint_text
        assert "0" in constraint_text


# =============================================================================
# Comprehensive Summary Tests
# =============================================================================


class TestAllModelsHaveExpectedConstraints:
    """Summary tests to verify all expected constraints are defined."""

    def test_nem_1492_enum_constraints_complete(self):
        """Test that all NEM-1492 enum-like constraints are defined."""
        expected = {
            ("Camera", "ck_cameras_status"),
            ("Event", "ck_events_risk_level"),
            ("Detection", "ck_detections_media_type"),
            ("Log", "ck_logs_level"),
            ("Log", "ck_logs_source"),
            ("AuditLog", "ck_audit_logs_status"),
        }
        models = {
            "Camera": Camera,
            "Event": Event,
            "Detection": Detection,
            "Log": Log,
            "AuditLog": AuditLog,
        }

        for model_name, constraint_name in expected:
            model_class = models[model_name]
            constraint_names = _get_check_constraint_names(model_class)
            assert constraint_name in constraint_names, (
                f"Missing NEM-1492 constraint: {model_name}.{constraint_name}"
            )

    def test_nem_1496_business_rule_constraints_complete(self):
        """Test that all NEM-1496 business rule constraints are defined."""
        expected = {
            ("Event", "ck_events_risk_score_range"),
            ("Event", "ck_events_time_order"),
            ("Detection", "ck_detections_confidence_range"),
            ("ActivityBaseline", "ck_activity_baselines_hour_range"),
            ("ActivityBaseline", "ck_activity_baselines_dow_range"),
            ("ClassBaseline", "ck_class_baselines_hour_range"),
            ("Zone", "ck_zones_priority_non_negative"),
            ("Zone", "ck_zones_color_hex"),
            ("SceneChange", "ck_scene_changes_similarity_range"),
            ("EventAudit", "ck_event_audits_context_score_range"),
            ("EventAudit", "ck_event_audits_reasoning_score_range"),
            ("EventAudit", "ck_event_audits_risk_justification_range"),
            ("EventAudit", "ck_event_audits_consistency_score_range"),
            ("EventAudit", "ck_event_audits_overall_score_range"),
            ("EventAudit", "ck_event_audits_enrichment_range"),
            ("AlertRule", "ck_alert_rules_risk_threshold_range"),
            ("AlertRule", "ck_alert_rules_min_confidence_range"),
            ("AlertRule", "ck_alert_rules_cooldown_non_negative"),
        }
        models = {
            "Event": Event,
            "Detection": Detection,
            "ActivityBaseline": ActivityBaseline,
            "ClassBaseline": ClassBaseline,
            "Zone": Zone,
            "SceneChange": SceneChange,
            "EventAudit": EventAudit,
            "AlertRule": AlertRule,
        }

        for model_name, constraint_name in expected:
            model_class = models[model_name]
            constraint_names = _get_check_constraint_names(model_class)
            assert constraint_name in constraint_names, (
                f"Missing NEM-1496 constraint: {model_name}.{constraint_name}"
            )
