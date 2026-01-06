"""Add CHECK constraints for enum-like columns and business rules

Revision ID: add_check_constraints
Revises: add_alerts_dedup_indexes
Create Date: 2026-01-06 13:00:00.000000

This migration adds database-level CHECK constraints for:

1. Enum-like string columns (NEM-1492):
   - cameras.status: online, offline, error, unknown
   - events.risk_level: low, medium, high, critical
   - detections.media_type: image, video
   - logs.level: DEBUG, INFO, WARNING, ERROR, CRITICAL
   - logs.source: backend, frontend
   - audit_logs.status: success, failure

2. Business rule validations (NEM-1496):
   - events.risk_score: 0-100 range
   - events.ended_at >= events.started_at
   - detections.confidence: 0.0-1.0 range
   - activity_baselines.hour: 0-23 range
   - activity_baselines.day_of_week: 0-6 range
   - class_baselines.hour: 0-23 range
   - zones.priority: non-negative
   - zones.color: hex format (#RRGGBB)
   - scene_changes.similarity_score: 0.0-1.0 range
   - event_audits quality scores: 1.0-5.0 range
   - alert_rules.risk_threshold: 0-100 range
   - alert_rules.min_confidence: 0.0-1.0 range
   - alert_rules.cooldown_seconds: non-negative
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_check_constraints"
down_revision: str | Sequence[str] | None = "add_alerts_dedup_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add CHECK constraints for enum-like columns and business rules."""
    # ==========================================================================
    # NEM-1492: CHECK constraints for enum-like string columns
    # ==========================================================================

    # cameras.status: online, offline, error, unknown
    op.create_check_constraint(
        "ck_cameras_status",
        "cameras",
        sa.text("status IN ('online', 'offline', 'error', 'unknown')"),
    )

    # events.risk_level: low, medium, high, critical (nullable)
    op.create_check_constraint(
        "ck_events_risk_level",
        "events",
        sa.text("risk_level IS NULL OR risk_level IN ('low', 'medium', 'high', 'critical')"),
    )

    # detections.media_type: image, video (nullable)
    op.create_check_constraint(
        "ck_detections_media_type",
        "detections",
        sa.text("media_type IS NULL OR media_type IN ('image', 'video')"),
    )

    # logs.level: DEBUG, INFO, WARNING, ERROR, CRITICAL
    op.create_check_constraint(
        "ck_logs_level",
        "logs",
        sa.text("level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')"),
    )

    # logs.source: backend, frontend
    op.create_check_constraint(
        "ck_logs_source",
        "logs",
        sa.text("source IN ('backend', 'frontend')"),
    )

    # audit_logs.status: success, failure
    op.create_check_constraint(
        "ck_audit_logs_status",
        "audit_logs",
        sa.text("status IN ('success', 'failure')"),
    )

    # ==========================================================================
    # NEM-1496: CHECK constraints for business rules
    # ==========================================================================

    # events.risk_score: 0-100 range (nullable)
    op.create_check_constraint(
        "ck_events_risk_score_range",
        "events",
        sa.text("risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 100)"),
    )

    # events.ended_at >= events.started_at (nullable ended_at)
    op.create_check_constraint(
        "ck_events_time_order",
        "events",
        sa.text("ended_at IS NULL OR ended_at >= started_at"),
    )

    # detections.confidence: 0.0-1.0 range (nullable)
    op.create_check_constraint(
        "ck_detections_confidence_range",
        "detections",
        sa.text("confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)"),
    )

    # activity_baselines.hour: 0-23 range
    op.create_check_constraint(
        "ck_activity_baselines_hour_range",
        "activity_baselines",
        sa.text("hour >= 0 AND hour <= 23"),
    )

    # activity_baselines.day_of_week: 0-6 range
    op.create_check_constraint(
        "ck_activity_baselines_dow_range",
        "activity_baselines",
        sa.text("day_of_week >= 0 AND day_of_week <= 6"),
    )

    # class_baselines.hour: 0-23 range
    op.create_check_constraint(
        "ck_class_baselines_hour_range",
        "class_baselines",
        sa.text("hour >= 0 AND hour <= 23"),
    )

    # Constraint: zones priority must be non-negative
    op.create_check_constraint(
        "ck_zones_priority_non_negative",
        "zones",
        sa.text("priority >= 0"),
    )

    # zones.color: hex format (#RRGGBB)
    # Using PostgreSQL regex for 6-character hex color
    op.create_check_constraint(
        "ck_zones_color_hex",
        "zones",
        sa.text("color ~ '^#[0-9A-Fa-f]{6}$'"),
    )

    # scene_changes.similarity_score: 0.0-1.0 range
    op.create_check_constraint(
        "ck_scene_changes_similarity_range",
        "scene_changes",
        sa.text("similarity_score >= 0.0 AND similarity_score <= 1.0"),
    )

    # event_audits quality scores: 1.0-5.0 range (nullable)
    op.create_check_constraint(
        "ck_event_audits_context_score_range",
        "event_audits",
        sa.text(
            "context_usage_score IS NULL OR "
            "(context_usage_score >= 1.0 AND context_usage_score <= 5.0)"
        ),
    )

    op.create_check_constraint(
        "ck_event_audits_reasoning_score_range",
        "event_audits",
        sa.text(
            "reasoning_coherence_score IS NULL OR "
            "(reasoning_coherence_score >= 1.0 AND reasoning_coherence_score <= 5.0)"
        ),
    )

    op.create_check_constraint(
        "ck_event_audits_risk_justification_range",
        "event_audits",
        sa.text(
            "risk_justification_score IS NULL OR "
            "(risk_justification_score >= 1.0 AND risk_justification_score <= 5.0)"
        ),
    )

    op.create_check_constraint(
        "ck_event_audits_consistency_score_range",
        "event_audits",
        sa.text(
            "consistency_score IS NULL OR (consistency_score >= 1.0 AND consistency_score <= 5.0)"
        ),
    )

    op.create_check_constraint(
        "ck_event_audits_overall_score_range",
        "event_audits",
        sa.text(
            "overall_quality_score IS NULL OR "
            "(overall_quality_score >= 1.0 AND overall_quality_score <= 5.0)"
        ),
    )

    # event_audits.enrichment_utilization: 0.0-1.0 range (percentage)
    op.create_check_constraint(
        "ck_event_audits_enrichment_range",
        "event_audits",
        sa.text("enrichment_utilization >= 0.0 AND enrichment_utilization <= 1.0"),
    )

    # alert_rules.risk_threshold: 0-100 range (nullable)
    op.create_check_constraint(
        "ck_alert_rules_risk_threshold_range",
        "alert_rules",
        sa.text("risk_threshold IS NULL OR (risk_threshold >= 0 AND risk_threshold <= 100)"),
    )

    # alert_rules.min_confidence: 0.0-1.0 range (nullable)
    op.create_check_constraint(
        "ck_alert_rules_min_confidence_range",
        "alert_rules",
        sa.text("min_confidence IS NULL OR (min_confidence >= 0.0 AND min_confidence <= 1.0)"),
    )

    # Constraint: alert_rules cooldown_seconds must be non-negative
    op.create_check_constraint(
        "ck_alert_rules_cooldown_non_negative",
        "alert_rules",
        sa.text("cooldown_seconds >= 0"),
    )


def downgrade() -> None:
    """Remove all CHECK constraints."""
    # Remove business rule constraints (NEM-1496)
    op.drop_constraint("ck_alert_rules_cooldown_non_negative", "alert_rules", type_="check")
    op.drop_constraint("ck_alert_rules_min_confidence_range", "alert_rules", type_="check")
    op.drop_constraint("ck_alert_rules_risk_threshold_range", "alert_rules", type_="check")
    op.drop_constraint("ck_event_audits_enrichment_range", "event_audits", type_="check")
    op.drop_constraint("ck_event_audits_overall_score_range", "event_audits", type_="check")
    op.drop_constraint("ck_event_audits_consistency_score_range", "event_audits", type_="check")
    op.drop_constraint("ck_event_audits_risk_justification_range", "event_audits", type_="check")
    op.drop_constraint("ck_event_audits_reasoning_score_range", "event_audits", type_="check")
    op.drop_constraint("ck_event_audits_context_score_range", "event_audits", type_="check")
    op.drop_constraint("ck_scene_changes_similarity_range", "scene_changes", type_="check")
    op.drop_constraint("ck_zones_color_hex", "zones", type_="check")
    op.drop_constraint("ck_zones_priority_non_negative", "zones", type_="check")
    op.drop_constraint("ck_class_baselines_hour_range", "class_baselines", type_="check")
    op.drop_constraint("ck_activity_baselines_dow_range", "activity_baselines", type_="check")
    op.drop_constraint("ck_activity_baselines_hour_range", "activity_baselines", type_="check")
    op.drop_constraint("ck_detections_confidence_range", "detections", type_="check")
    op.drop_constraint("ck_events_time_order", "events", type_="check")
    op.drop_constraint("ck_events_risk_score_range", "events", type_="check")

    # Remove enum-like constraints (NEM-1492)
    op.drop_constraint("ck_audit_logs_status", "audit_logs", type_="check")
    op.drop_constraint("ck_logs_source", "logs", type_="check")
    op.drop_constraint("ck_logs_level", "logs", type_="check")
    op.drop_constraint("ck_detections_media_type", "detections", type_="check")
    op.drop_constraint("ck_events_risk_level", "events", type_="check")
    op.drop_constraint("ck_cameras_status", "cameras", type_="check")
