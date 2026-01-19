"""initial_schema

Revision ID: e36700c35af6
Revises:
Create Date: 2026-01-18 23:06:57.700345

This migration creates the complete initial schema for the home security
intelligence system. All tables are created from scratch based on the
SQLAlchemy models.

Tables created (in dependency order):
- Base tables: cameras, alert_rules, audit_logs, logs, gpu_stats, jobs,
  job_attempts, job_logs, job_transitions, export_jobs, notification_preferences,
  quiet_hours_periods, prompt_configs, user_calibration, entities, summaries
- Dependent tables: zones, detections, events, event_detections, event_audits,
  event_feedback, alerts, activity_baselines, class_baselines, scene_changes,
  camera_notification_settings
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e36700c35af6"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all tables for the home security intelligence system."""

    # =========================================================================
    # ENUM TYPES
    # =========================================================================

    # Create enum types
    op.execute("CREATE TYPE alert_severity AS ENUM ('low', 'medium', 'high', 'critical')")
    op.execute(
        "CREATE TYPE alert_status AS ENUM ('pending', 'delivered', 'acknowledged', 'dismissed')"
    )
    op.execute(
        "CREATE TYPE export_job_status AS ENUM ('pending', 'running', 'completed', 'failed')"
    )
    op.execute(
        "CREATE TYPE zone_type_enum AS ENUM ('entry_point', 'driveway', 'sidewalk', 'yard', 'other')"
    )
    op.execute("CREATE TYPE zone_shape_enum AS ENUM ('rectangle', 'polygon')")
    op.execute(
        "CREATE TYPE scene_change_type_enum AS ENUM ('view_blocked', 'angle_changed', 'view_tampered', 'unknown')"
    )

    # =========================================================================
    # BASE TABLES (no foreign keys)
    # =========================================================================

    # cameras
    op.create_table(
        "cameras",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("folder_path", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="online"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('online', 'offline', 'error', 'unknown')", name="ck_cameras_status"
        ),
    )
    op.create_index("idx_cameras_name_unique", "cameras", ["name"], unique=True)
    op.create_index("idx_cameras_folder_path_unique", "cameras", ["folder_path"], unique=True)

    # alert_rules
    op.create_table(
        "alert_rules",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "severity",
            postgresql.ENUM(
                "low", "medium", "high", "critical", name="alert_severity", create_type=False
            ),
            nullable=False,
            server_default="medium",
        ),
        sa.Column("risk_threshold", sa.Integer(), nullable=True),
        sa.Column("object_types", postgresql.JSON(), nullable=True),
        sa.Column("camera_ids", postgresql.JSON(), nullable=True),
        sa.Column("zone_ids", postgresql.JSON(), nullable=True),
        sa.Column("min_confidence", sa.Float(), nullable=True),
        sa.Column("schedule", postgresql.JSON(), nullable=True),
        sa.Column("conditions", postgresql.JSON(), nullable=True),
        sa.Column(
            "dedup_key_template",
            sa.String(255),
            nullable=False,
            server_default="{camera_id}:{rule_id}",
        ),
        sa.Column("cooldown_seconds", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("channels", postgresql.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "risk_threshold IS NULL OR (risk_threshold >= 0 AND risk_threshold <= 100)",
            name="ck_alert_rules_risk_threshold_range",
        ),
        sa.CheckConstraint(
            "min_confidence IS NULL OR (min_confidence >= 0.0 AND min_confidence <= 1.0)",
            name="ck_alert_rules_min_confidence_range",
        ),
        sa.CheckConstraint("cooldown_seconds >= 0", name="ck_alert_rules_cooldown_non_negative"),
    )
    op.create_index("idx_alert_rules_name", "alert_rules", ["name"])
    op.create_index("idx_alert_rules_enabled", "alert_rules", ["enabled"])
    op.create_index("idx_alert_rules_severity", "alert_rules", ["severity"])

    # audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="success"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("status IN ('success', 'failure')", name="ck_audit_logs_status"),
    )
    op.create_index("idx_audit_logs_timestamp", "audit_logs", ["timestamp"])
    op.create_index("idx_audit_logs_action", "audit_logs", ["action"])
    op.create_index("idx_audit_logs_resource_type", "audit_logs", ["resource_type"])
    op.create_index("idx_audit_logs_actor", "audit_logs", ["actor"])
    op.create_index("idx_audit_logs_status", "audit_logs", ["status"])
    op.create_index("idx_audit_logs_resource", "audit_logs", ["resource_type", "resource_id"])
    op.create_index(
        "ix_audit_logs_timestamp_brin", "audit_logs", ["timestamp"], postgresql_using="brin"
    )

    # logs
    op.create_table(
        "logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("level", sa.String(10), nullable=False),
        sa.Column("component", sa.String(50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("camera_id", sa.String(100), nullable=True),
        sa.Column("event_id", sa.Integer(), nullable=True),
        sa.Column("request_id", sa.String(36), nullable=True),
        sa.Column("detection_id", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("extra", postgresql.JSONB(), nullable=True),
        sa.Column("source", sa.String(10), nullable=False, server_default="backend"),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')", name="ck_logs_level"
        ),
        sa.CheckConstraint("source IN ('backend', 'frontend')", name="ck_logs_source"),
    )
    op.create_index("idx_logs_timestamp", "logs", ["timestamp"])
    op.create_index("idx_logs_level", "logs", ["level"])
    op.create_index("idx_logs_component", "logs", ["component"])
    op.create_index("idx_logs_camera_id", "logs", ["camera_id"])
    op.create_index("idx_logs_source", "logs", ["source"])
    op.create_index("ix_logs_timestamp_brin", "logs", ["timestamp"], postgresql_using="brin")
    op.create_index("idx_logs_search_vector", "logs", ["search_vector"], postgresql_using="gin")

    # gpu_stats
    op.create_table(
        "gpu_stats",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("gpu_name", sa.String(255), nullable=True),
        sa.Column("gpu_utilization", sa.Float(), nullable=True),
        sa.Column("memory_used", sa.Integer(), nullable=True),
        sa.Column("memory_total", sa.Integer(), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("power_usage", sa.Float(), nullable=True),
        sa.Column("inference_fps", sa.Float(), nullable=True),
        sa.Column("fan_speed", sa.Integer(), nullable=True),
        sa.Column("sm_clock", sa.Integer(), nullable=True),
        sa.Column("memory_bandwidth_utilization", sa.Float(), nullable=True),
        sa.Column("pstate", sa.Integer(), nullable=True),
        sa.Column("throttle_reasons", sa.Integer(), nullable=True),
        sa.Column("power_limit", sa.Float(), nullable=True),
        sa.Column("sm_clock_max", sa.Integer(), nullable=True),
        sa.Column("compute_processes_count", sa.Integer(), nullable=True),
        sa.Column("pcie_replay_counter", sa.Integer(), nullable=True),
        sa.Column("temp_slowdown_threshold", sa.Float(), nullable=True),
        sa.Column("memory_clock", sa.Integer(), nullable=True),
        sa.Column("memory_clock_max", sa.Integer(), nullable=True),
        sa.Column("pcie_link_gen", sa.Integer(), nullable=True),
        sa.Column("pcie_link_width", sa.Integer(), nullable=True),
        sa.Column("pcie_tx_throughput", sa.Integer(), nullable=True),
        sa.Column("pcie_rx_throughput", sa.Integer(), nullable=True),
        sa.Column("encoder_utilization", sa.Integer(), nullable=True),
        sa.Column("decoder_utilization", sa.Integer(), nullable=True),
        sa.Column("bar1_used", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_gpu_stats_recorded_at_brin", "gpu_stats", ["recorded_at"], postgresql_using="brin"
    )

    # jobs
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("job_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("queue_name", sa.String(100), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="2"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_step", sa.String(255), nullable=True),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_traceback", sa.Text(), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_jobs_status",
        ),
        sa.CheckConstraint(
            "progress_percent >= 0 AND progress_percent <= 100", name="ck_jobs_progress_range"
        ),
        sa.CheckConstraint("priority >= 0 AND priority <= 4", name="ck_jobs_priority_range"),
        sa.CheckConstraint("attempt_number >= 1", name="ck_jobs_attempt_number_min"),
        sa.CheckConstraint("max_attempts >= 1", name="ck_jobs_max_attempts_min"),
        sa.CheckConstraint(
            "completed_at IS NULL OR completed_at >= created_at",
            name="ck_jobs_completed_after_created",
        ),
        sa.CheckConstraint(
            "started_at IS NULL OR started_at >= created_at", name="ck_jobs_started_after_created"
        ),
    )
    op.create_index("idx_jobs_status", "jobs", ["status"])
    op.create_index("idx_jobs_job_type", "jobs", ["job_type"])
    op.create_index("idx_jobs_created_at", "jobs", ["created_at"])
    op.create_index("idx_jobs_queue_name", "jobs", ["queue_name"])
    op.create_index("idx_jobs_priority", "jobs", ["priority"])
    op.create_index("idx_jobs_status_created_at", "jobs", ["status", "created_at"])
    op.create_index("idx_jobs_job_type_status", "jobs", ["job_type", "status"])
    op.create_index("ix_jobs_created_at_brin", "jobs", ["created_at"], postgresql_using="brin")

    # job_attempts
    op.create_table(
        "job_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="started"),
        sa.Column("worker_id", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_traceback", sa.Text(), nullable=True),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('started', 'succeeded', 'failed', 'cancelled')",
            name="ck_job_attempts_status",
        ),
        sa.CheckConstraint("attempt_number >= 1", name="ck_job_attempts_attempt_number"),
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at", name="ck_job_attempts_time_order"
        ),
    )
    op.create_index("ix_job_attempts_job_id", "job_attempts", ["job_id"])
    op.create_index("idx_job_attempts_job_attempt", "job_attempts", ["job_id", "attempt_number"])
    op.create_index("idx_job_attempts_status", "job_attempts", ["status"])
    op.create_index(
        "ix_job_attempts_started_at_brin", "job_attempts", ["started_at"], postgresql_using="brin"
    )

    # job_logs
    op.create_table(
        "job_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("level", sa.String(10), nullable=False, server_default="info"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("context", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "level IN ('debug', 'info', 'warning', 'error')", name="ck_job_logs_level"
        ),
        sa.CheckConstraint("attempt_number >= 1", name="ck_job_logs_attempt_number"),
    )
    op.create_index("ix_job_logs_job_id", "job_logs", ["job_id"])
    op.create_index("idx_job_logs_job_attempt", "job_logs", ["job_id", "attempt_number"])
    op.create_index("idx_job_logs_level", "job_logs", ["level"])
    op.create_index("idx_job_logs_job_timestamp", "job_logs", ["job_id", "timestamp"])
    op.create_index(
        "ix_job_logs_timestamp_brin", "job_logs", ["timestamp"], postgresql_using="brin"
    )

    # job_transitions
    op.create_table(
        "job_transitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", sa.String(36), nullable=False),
        sa.Column("from_status", sa.String(50), nullable=False),
        sa.Column("to_status", sa.String(50), nullable=False),
        sa.Column(
            "transitioned_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("triggered_by", sa.String(50), nullable=False, server_default="worker"),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_job_transitions_job_id", "job_transitions", ["job_id"])
    op.create_index("ix_job_transitions_job_id", "job_transitions", ["job_id"])
    op.create_index("idx_job_transitions_transitioned_at", "job_transitions", ["transitioned_at"])
    op.create_index(
        "idx_job_transitions_job_id_transitioned_at",
        "job_transitions",
        ["job_id", "transitioned_at"],
    )

    # export_jobs
    op.create_table(
        "export_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "running",
                "completed",
                "failed",
                name="export_job_status",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("export_type", sa.String(50), nullable=False),
        sa.Column("export_format", sa.String(20), nullable=False, server_default="csv"),
        sa.Column("total_items", sa.Integer(), nullable=True),
        sa.Column("processed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_step", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("estimated_completion", sa.DateTime(timezone=True), nullable=True),
        sa.Column("output_path", sa.String(512), nullable=True),
        sa.Column("output_size_bytes", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("filter_params", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "progress_percent >= 0 AND progress_percent <= 100",
            name="ck_export_jobs_progress_range",
        ),
        sa.CheckConstraint("processed_items >= 0", name="ck_export_jobs_processed_non_negative"),
        sa.CheckConstraint(
            "total_items IS NULL OR total_items >= 0", name="ck_export_jobs_total_non_negative"
        ),
        sa.CheckConstraint(
            "output_size_bytes IS NULL OR output_size_bytes >= 0",
            name="ck_export_jobs_size_non_negative",
        ),
    )
    op.create_index("idx_export_jobs_status", "export_jobs", ["status"])
    op.create_index("idx_export_jobs_export_type", "export_jobs", ["export_type"])
    op.create_index("idx_export_jobs_created_at", "export_jobs", ["created_at"])
    op.create_index("idx_export_jobs_status_created_at", "export_jobs", ["status", "created_at"])

    # Notification preferences - singleton table with id=1 constraint
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("sound", sa.String(), nullable=False),
        sa.Column("risk_filters", postgresql.ARRAY(sa.String()), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("id = 1", name="ck_notification_preferences_singleton"),
        sa.CheckConstraint(
            "sound IN ('none', 'default', 'alert', 'chime', 'urgent')",
            name="ck_notification_preferences_sound",
        ),
    )

    # quiet_hours_periods
    op.create_table(
        "quiet_hours_periods",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("days", postgresql.ARRAY(sa.String()), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_quiet_hours_periods_start_end", "quiet_hours_periods", ["start_time", "end_time"]
    )

    # prompt_configs
    op.create_table(
        "prompt_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("model", sa.String(50), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("max_tokens", sa.Integer(), nullable=False, server_default="2048"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_prompt_configs_model", "prompt_configs", ["model"], unique=True)
    op.create_index("idx_prompt_configs_updated_at", "prompt_configs", ["updated_at"])

    # user_calibration
    op.create_table(
        "user_calibration",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("low_threshold", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("medium_threshold", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("high_threshold", sa.Integer(), nullable=False, server_default="85"),
        sa.Column("decay_factor", sa.Float(), nullable=False, server_default="0.1"),
        sa.Column("correct_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("false_positive_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("missed_threat_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("severity_wrong_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
        sa.CheckConstraint(
            "low_threshold >= 0 AND low_threshold <= 100", name="ck_user_calibration_low_range"
        ),
        sa.CheckConstraint(
            "medium_threshold >= 0 AND medium_threshold <= 100",
            name="ck_user_calibration_medium_range",
        ),
        sa.CheckConstraint(
            "high_threshold >= 0 AND high_threshold <= 100", name="ck_user_calibration_high_range"
        ),
        sa.CheckConstraint(
            "low_threshold < medium_threshold AND medium_threshold < high_threshold",
            name="ck_user_calibration_threshold_order",
        ),
        sa.CheckConstraint(
            "decay_factor >= 0.0 AND decay_factor <= 1.0", name="ck_user_calibration_decay_range"
        ),
        sa.CheckConstraint("correct_count >= 0", name="ck_user_calibration_correct_count"),
        sa.CheckConstraint("false_positive_count >= 0", name="ck_user_calibration_fp_count"),
        sa.CheckConstraint("missed_threat_count >= 0", name="ck_user_calibration_mt_count"),
        sa.CheckConstraint("severity_wrong_count >= 0", name="ck_user_calibration_sw_count"),
    )
    op.create_index("idx_user_calibration_user_id", "user_calibration", ["user_id"])

    # entities
    op.create_table(
        "entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(20), nullable=False, server_default="person"),
        sa.Column("trust_status", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("embedding_vector", postgresql.JSONB(), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("detection_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("entity_metadata", postgresql.JSONB(), nullable=True),
        sa.Column("primary_detection_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "entity_type IN ('person', 'vehicle', 'animal', 'package', 'other')",
            name="ck_entities_entity_type",
        ),
        sa.CheckConstraint(
            "trust_status IN ('trusted', 'untrusted', 'unknown')", name="ck_entities_trust_status"
        ),
        sa.CheckConstraint("detection_count >= 0", name="ck_entities_detection_count"),
    )
    op.create_index("ix_entities_primary_detection_id", "entities", ["primary_detection_id"])
    op.create_index("idx_entities_entity_type", "entities", ["entity_type"])
    op.create_index("idx_entities_trust_status", "entities", ["trust_status"])
    op.create_index("idx_entities_first_seen_at", "entities", ["first_seen_at"])
    op.create_index("idx_entities_last_seen_at", "entities", ["last_seen_at"])
    op.create_index("idx_entities_type_last_seen", "entities", ["entity_type", "last_seen_at"])
    op.create_index(
        "ix_entities_entity_metadata_gin",
        "entities",
        ["entity_metadata"],
        postgresql_using="gin",
        postgresql_ops={"entity_metadata": "jsonb_path_ops"},
    )

    # summaries (NEW - dashboard summary cards)
    op.create_table(
        "summaries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("summary_type", sa.String(10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False),
        sa.Column("event_ids", postgresql.ARRAY(sa.Integer()), nullable=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("summary_type IN ('hourly', 'daily')", name="summaries_type_check"),
    )
    op.create_index("idx_summaries_type_created", "summaries", ["summary_type", "created_at"])
    op.create_index("idx_summaries_created_at", "summaries", ["created_at"])

    # =========================================================================
    # TABLES WITH FOREIGN KEYS TO cameras
    # =========================================================================

    # zones
    op.create_table(
        "zones",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("camera_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "zone_type",
            postgresql.ENUM(
                "entry_point",
                "driveway",
                "sidewalk",
                "yard",
                "other",
                name="zone_type_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="other",
        ),
        sa.Column("coordinates", postgresql.JSONB(), nullable=False),
        sa.Column(
            "shape",
            postgresql.ENUM("rectangle", "polygon", name="zone_shape_enum", create_type=False),
            nullable=False,
            server_default="rectangle",
        ),
        sa.Column("color", sa.String(7), nullable=False, server_default="#3B82F6"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.id"], ondelete="CASCADE"),
        sa.CheckConstraint("priority >= 0", name="ck_zones_priority_non_negative"),
        sa.CheckConstraint("color ~ '^#[0-9A-Fa-f]{6}$'", name="ck_zones_color_hex"),
    )
    op.create_index("idx_zones_camera_id", "zones", ["camera_id"])
    op.create_index("idx_zones_enabled", "zones", ["enabled"])
    op.create_index("idx_zones_camera_enabled", "zones", ["camera_id", "enabled"])

    # detections
    op.create_table(
        "detections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("camera_id", sa.String(), nullable=False),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("file_type", sa.String(), nullable=True),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("object_type", sa.String(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("bbox_x", sa.Integer(), nullable=True),
        sa.Column("bbox_y", sa.Integer(), nullable=True),
        sa.Column("bbox_width", sa.Integer(), nullable=True),
        sa.Column("bbox_height", sa.Integer(), nullable=True),
        sa.Column("thumbnail_path", sa.String(), nullable=True),
        sa.Column("media_type", sa.String(), nullable=True, server_default="image"),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("video_codec", sa.String(), nullable=True),
        sa.Column("video_width", sa.Integer(), nullable=True),
        sa.Column("video_height", sa.Integer(), nullable=True),
        sa.Column("enrichment_data", postgresql.JSONB(), nullable=True),
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
        sa.Column("labels", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "media_type IS NULL OR media_type IN ('image', 'video')",
            name="ck_detections_media_type",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)",
            name="ck_detections_confidence_range",
        ),
    )
    op.create_index("idx_detections_camera_id", "detections", ["camera_id"])
    op.create_index("idx_detections_detected_at", "detections", ["detected_at"])
    op.create_index("idx_detections_camera_time", "detections", ["camera_id", "detected_at"])
    op.create_index("idx_detections_camera_object_type", "detections", ["camera_id", "object_type"])
    op.create_index(
        "ix_detections_object_type_detected_at", "detections", ["object_type", "detected_at"]
    )
    op.create_index(
        "ix_detections_enrichment_data_gin",
        "detections",
        ["enrichment_data"],
        postgresql_using="gin",
        postgresql_ops={"enrichment_data": "jsonb_path_ops"},
    )
    op.create_index(
        "ix_detections_detected_at_brin", "detections", ["detected_at"], postgresql_using="brin"
    )

    # events
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("batch_id", sa.String(), nullable=False),
        sa.Column("camera_id", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("risk_score", sa.Integer(), nullable=True),
        sa.Column("risk_level", sa.String(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("llm_prompt", sa.Text(), nullable=True),
        sa.Column("reviewed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_fast_path", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("object_types", sa.Text(), nullable=True),
        sa.Column("clip_path", sa.String(), nullable=True),
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("snooze_until", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "risk_level IS NULL OR risk_level IN ('low', 'medium', 'high', 'critical')",
            name="ck_events_risk_level",
        ),
        sa.CheckConstraint(
            "risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 100)",
            name="ck_events_risk_score_range",
        ),
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at", name="ck_events_time_order"
        ),
    )
    op.create_index("idx_events_camera_id", "events", ["camera_id"])
    op.create_index("idx_events_started_at", "events", ["started_at"])
    op.create_index("idx_events_risk_score", "events", ["risk_score"])
    op.create_index("idx_events_reviewed", "events", ["reviewed"])
    op.create_index("idx_events_batch_id", "events", ["batch_id"])
    op.create_index("idx_events_search_vector", "events", ["search_vector"], postgresql_using="gin")
    op.create_index("idx_events_risk_level_started_at", "events", ["risk_level", "started_at"])
    op.create_index(
        "idx_events_export_covering",
        "events",
        [
            "started_at",
            "id",
            "ended_at",
            "risk_level",
            "risk_score",
            "camera_id",
            "object_types",
            "summary",
        ],
    )
    op.create_index(
        "idx_events_unreviewed", "events", ["id"], postgresql_where=sa.text("reviewed = false")
    )
    op.create_index("ix_events_started_at_brin", "events", ["started_at"], postgresql_using="brin")

    # activity_baselines
    op.create_table(
        "activity_baselines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("camera_id", sa.String(), nullable=False),
        sa.Column("hour", sa.Integer(), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("avg_count", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "last_updated",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("camera_id", "hour", "day_of_week", name="uq_activity_baseline_slot"),
        sa.CheckConstraint("hour >= 0 AND hour <= 23", name="ck_activity_baselines_hour_range"),
        sa.CheckConstraint(
            "day_of_week >= 0 AND day_of_week <= 6", name="ck_activity_baselines_dow_range"
        ),
    )
    op.create_index("idx_activity_baseline_camera", "activity_baselines", ["camera_id"])
    op.create_index(
        "idx_activity_baseline_slot", "activity_baselines", ["camera_id", "hour", "day_of_week"]
    )

    # class_baselines
    op.create_table(
        "class_baselines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("camera_id", sa.String(), nullable=False),
        sa.Column("detection_class", sa.String(), nullable=False),
        sa.Column("hour", sa.Integer(), nullable=False),
        sa.Column("frequency", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "last_updated",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("camera_id", "detection_class", "hour", name="uq_class_baseline_slot"),
        sa.CheckConstraint("hour >= 0 AND hour <= 23", name="ck_class_baselines_hour_range"),
    )
    op.create_index("idx_class_baseline_camera", "class_baselines", ["camera_id"])
    op.create_index("idx_class_baseline_class", "class_baselines", ["camera_id", "detection_class"])
    op.create_index(
        "idx_class_baseline_slot", "class_baselines", ["camera_id", "detection_class", "hour"]
    )

    # scene_changes
    op.create_table(
        "scene_changes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("camera_id", sa.String(), nullable=False),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "change_type",
            postgresql.ENUM(
                "view_blocked",
                "angle_changed",
                "view_tampered",
                "unknown",
                name="scene_change_type_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("similarity_score", sa.Float(), nullable=False),
        sa.Column("acknowledged", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("file_path", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "similarity_score >= 0.0 AND similarity_score <= 1.0",
            name="ck_scene_changes_similarity_range",
        ),
    )
    op.create_index("idx_scene_changes_camera_id", "scene_changes", ["camera_id"])
    op.create_index("idx_scene_changes_detected_at", "scene_changes", ["detected_at"])
    op.create_index("idx_scene_changes_acknowledged", "scene_changes", ["acknowledged"])
    op.create_index(
        "idx_scene_changes_camera_acknowledged", "scene_changes", ["camera_id", "acknowledged"]
    )
    op.create_index(
        "ix_scene_changes_detected_at_brin",
        "scene_changes",
        ["detected_at"],
        postgresql_using="brin",
    )
    op.create_index(
        "idx_scene_changes_acknowledged_false",
        "scene_changes",
        ["acknowledged"],
        postgresql_where=sa.text("acknowledged = false"),
    )

    # camera_notification_settings
    op.create_table(
        "camera_notification_settings",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("camera_id", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("risk_threshold", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "risk_threshold >= 0 AND risk_threshold <= 100",
            name="ck_camera_notification_settings_risk_threshold",
        ),
    )
    op.create_index(
        "idx_camera_notification_settings_camera_id",
        "camera_notification_settings",
        ["camera_id"],
        unique=True,
    )

    # =========================================================================
    # TABLES WITH FOREIGN KEYS TO events
    # =========================================================================

    # alerts
    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("rule_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column(
            "severity",
            postgresql.ENUM(
                "low", "medium", "high", "critical", name="alert_severity", create_type=False
            ),
            nullable=False,
            server_default="medium",
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "delivered",
                "acknowledged",
                "dismissed",
                name="alert_status",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("channels", postgresql.JSON(), nullable=True),
        sa.Column("dedup_key", sa.String(255), nullable=False),
        sa.Column("metadata", postgresql.JSON(), nullable=True),
        sa.Column("version_id", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rule_id"], ["alert_rules.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_alerts_event_id", "alerts", ["event_id"])
    op.create_index("idx_alerts_rule_id", "alerts", ["rule_id"])
    op.create_index("idx_alerts_severity", "alerts", ["severity"])
    op.create_index("idx_alerts_status", "alerts", ["status"])
    op.create_index("idx_alerts_created_at", "alerts", ["created_at"])
    op.create_index("idx_alerts_dedup_key", "alerts", ["dedup_key"])
    op.create_index("idx_alerts_dedup_key_created_at", "alerts", ["dedup_key", "created_at"])
    op.create_index("idx_alerts_delivered_at", "alerts", ["delivered_at"])
    op.create_index(
        "idx_alerts_event_rule_delivered", "alerts", ["event_id", "rule_id", "delivered_at"]
    )

    # event_audits
    op.create_table(
        "event_audits",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column(
            "audited_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("has_rtdetr", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("has_florence", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("has_clip", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("has_violence", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("has_clothing", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("has_vehicle", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("has_pet", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("has_weather", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "has_image_quality", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("has_zones", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("has_baseline", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "has_cross_camera", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("prompt_length", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prompt_token_estimate", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("enrichment_utilization", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("context_usage_score", sa.Float(), nullable=True),
        sa.Column("reasoning_coherence_score", sa.Float(), nullable=True),
        sa.Column("risk_justification_score", sa.Float(), nullable=True),
        sa.Column("consistency_score", sa.Float(), nullable=True),
        sa.Column("overall_quality_score", sa.Float(), nullable=True),
        sa.Column("consistency_risk_score", sa.Integer(), nullable=True),
        sa.Column("consistency_diff", sa.Integer(), nullable=True),
        sa.Column("self_eval_critique", sa.Text(), nullable=True),
        sa.Column("self_eval_prompt", sa.Text(), nullable=True),
        sa.Column("self_eval_response", sa.Text(), nullable=True),
        sa.Column("missing_context", sa.Text(), nullable=True),
        sa.Column("confusing_sections", sa.Text(), nullable=True),
        sa.Column("unused_data", sa.Text(), nullable=True),
        sa.Column("format_suggestions", sa.Text(), nullable=True),
        sa.Column("model_gaps", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("event_id"),
        sa.CheckConstraint(
            "context_usage_score IS NULL OR (context_usage_score >= 1.0 AND context_usage_score <= 5.0)",
            name="ck_event_audits_context_score_range",
        ),
        sa.CheckConstraint(
            "reasoning_coherence_score IS NULL OR (reasoning_coherence_score >= 1.0 AND reasoning_coherence_score <= 5.0)",
            name="ck_event_audits_reasoning_score_range",
        ),
        sa.CheckConstraint(
            "risk_justification_score IS NULL OR (risk_justification_score >= 1.0 AND risk_justification_score <= 5.0)",
            name="ck_event_audits_risk_justification_range",
        ),
        sa.CheckConstraint(
            "consistency_score IS NULL OR (consistency_score >= 1.0 AND consistency_score <= 5.0)",
            name="ck_event_audits_consistency_score_range",
        ),
        sa.CheckConstraint(
            "overall_quality_score IS NULL OR (overall_quality_score >= 1.0 AND overall_quality_score <= 5.0)",
            name="ck_event_audits_overall_score_range",
        ),
        sa.CheckConstraint(
            "enrichment_utilization >= 0.0 AND enrichment_utilization <= 1.0",
            name="ck_event_audits_enrichment_range",
        ),
    )
    op.create_index("idx_event_audits_event_id", "event_audits", ["event_id"])
    op.create_index("idx_event_audits_audited_at", "event_audits", ["audited_at"])
    op.create_index("idx_event_audits_overall_score", "event_audits", ["overall_quality_score"])

    # event_feedback
    op.create_table(
        "event_feedback",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("feedback_type", sa.String(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("expected_severity", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("event_id"),
        sa.CheckConstraint(
            "feedback_type IN ('accurate', 'correct', 'false_positive', 'missed_threat', 'severity_wrong')",
            name="ck_event_feedback_type",
        ),
        sa.CheckConstraint(
            "expected_severity IS NULL OR expected_severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_event_feedback_expected_severity",
        ),
    )
    op.create_index("idx_event_feedback_event_id", "event_feedback", ["event_id"])
    op.create_index("idx_event_feedback_type", "event_feedback", ["feedback_type"])
    op.create_index("idx_event_feedback_created_at", "event_feedback", ["created_at"])

    # =========================================================================
    # JUNCTION TABLES
    # =========================================================================

    # event_detections (junction table for events <-> detections)
    op.create_table(
        "event_detections",
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("detection_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("event_id", "detection_id"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["detection_id"], ["detections.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_event_detections_event_id", "event_detections", ["event_id"])
    op.create_index("idx_event_detections_detection_id", "event_detections", ["detection_id"])
    op.create_index("idx_event_detections_created_at", "event_detections", ["created_at"])


def downgrade() -> None:
    """Drop all tables in reverse order."""

    # Junction tables
    op.drop_table("event_detections")

    # Tables with FK to events
    op.drop_table("event_feedback")
    op.drop_table("event_audits")
    op.drop_table("alerts")

    # Tables with FK to cameras
    op.drop_table("camera_notification_settings")
    op.drop_table("scene_changes")
    op.drop_table("class_baselines")
    op.drop_table("activity_baselines")
    op.drop_table("events")
    op.drop_table("detections")
    op.drop_table("zones")

    # Base tables
    op.drop_table("summaries")
    op.drop_table("entities")
    op.drop_table("user_calibration")
    op.drop_table("prompt_configs")
    op.drop_table("quiet_hours_periods")
    op.drop_table("notification_preferences")
    op.drop_table("export_jobs")
    op.drop_table("job_transitions")
    op.drop_table("job_logs")
    op.drop_table("job_attempts")
    op.drop_table("jobs")
    op.drop_table("gpu_stats")
    op.drop_table("logs")
    op.drop_table("audit_logs")
    op.drop_table("alert_rules")
    op.drop_table("cameras")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS scene_change_type_enum")
    op.execute("DROP TYPE IF EXISTS zone_shape_enum")
    op.execute("DROP TYPE IF EXISTS zone_type_enum")
    op.execute("DROP TYPE IF EXISTS export_job_status")
    op.execute("DROP TYPE IF EXISTS alert_status")
    op.execute("DROP TYPE IF EXISTS alert_severity")
