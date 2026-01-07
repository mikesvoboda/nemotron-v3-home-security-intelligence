"""Add notification preferences tables

Revision ID: add_notification_preferences
Revises: add_detections_obj_type_time_idx
Create Date: 2026-01-07 00:00:00.000000

This migration adds tables for notification preferences configuration:
- notification_preferences: Global notification settings (singleton table)
- camera_notification_settings: Per-camera notification settings
- quiet_hours_periods: Quiet hours configuration

These tables enable users to configure:
- Which risk levels trigger notifications
- Per-camera notification toggles and risk thresholds
- Quiet hours periods (time ranges when notifications are muted)
- Notification sound preferences

Related issue:
- NEM-1798: Notification Preferences Panel
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_notification_preferences"
down_revision: str | Sequence[str] | None = "add_detections_obj_type_time_idx"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add notification preferences tables."""
    # Create notification_preferences table (singleton)
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "sound",
            sa.String(),
            nullable=False,
            server_default=sa.text("'default'"),
        ),
        sa.Column(
            "risk_filters",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("ARRAY['critical', 'high', 'medium']::varchar[]"),
        ),
        sa.CheckConstraint("id = 1", name="ck_notification_preferences_singleton"),
        sa.CheckConstraint(
            "sound IN ('none', 'default', 'alert', 'chime', 'urgent')",
            name="ck_notification_preferences_sound",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create camera_notification_settings table
    op.create_table(
        "camera_notification_settings",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("camera_id", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("risk_threshold", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.CheckConstraint(
            "risk_threshold >= 0 AND risk_threshold <= 100",
            name="ck_camera_notification_settings_risk_threshold",
        ),
        sa.ForeignKeyConstraint(
            ["camera_id"],
            ["cameras.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_camera_notification_settings_camera_id",
        "camera_notification_settings",
        ["camera_id"],
        unique=True,
    )

    # Create quiet_hours_periods table
    op.create_table(
        "quiet_hours_periods",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column(
            "days",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text(
                "ARRAY['monday', 'tuesday', 'wednesday', 'thursday', 'friday', "
                "'saturday', 'sunday']::varchar[]"
            ),
        ),
        sa.CheckConstraint("start_time < end_time", name="ck_quiet_hours_periods_time_range"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_quiet_hours_periods_start_end",
        "quiet_hours_periods",
        ["start_time", "end_time"],
        unique=False,
    )

    # Insert default notification preferences row
    op.execute(
        """
        INSERT INTO notification_preferences (id, enabled, sound, risk_filters)
        VALUES (1, true, 'default', ARRAY['critical', 'high', 'medium']::varchar[])
        """
    )


def downgrade() -> None:
    """Remove notification preferences tables."""
    op.drop_index("idx_quiet_hours_periods_start_end", table_name="quiet_hours_periods")
    op.drop_table("quiet_hours_periods")
    op.drop_index(
        "idx_camera_notification_settings_camera_id",
        table_name="camera_notification_settings",
    )
    op.drop_table("camera_notification_settings")
    op.drop_table("notification_preferences")
