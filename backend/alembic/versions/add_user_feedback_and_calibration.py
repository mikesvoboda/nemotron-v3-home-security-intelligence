"""Add user feedback and calibration tables

Revision ID: add_user_feedback_calibration
Revises: drop_detection_ids_column
Create Date: 2026-01-08 14:00:00.000000

This migration adds tables for:
1. event_feedback - User feedback on events (false positives, missed detections)
2. user_calibration - Personalized risk thresholds per user

Related Linear issue: NEM-1794
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_user_feedback_calibration"
down_revision: str | Sequence[str] | None = "drop_detection_ids_column"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create event_feedback and user_calibration tables."""
    # Create event_feedback table
    op.create_table(
        "event_feedback",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("feedback_type", sa.String(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name="fk_event_feedback_event_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("event_id", name="uq_event_feedback_event_id"),
        sa.CheckConstraint(
            "feedback_type IN ('false_positive', 'missed_detection')",
            name="ck_event_feedback_type",
        ),
    )

    # Create indexes for event_feedback
    op.create_index("idx_event_feedback_event_id", "event_feedback", ["event_id"])
    op.create_index("idx_event_feedback_type", "event_feedback", ["feedback_type"])
    op.create_index("idx_event_feedback_created_at", "event_feedback", ["created_at"])

    # Create user_calibration table
    op.create_table(
        "user_calibration",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("low_threshold", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("medium_threshold", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("high_threshold", sa.Integer(), nullable=False, server_default="85"),
        sa.Column("decay_factor", sa.Float(), nullable=False, server_default="0.1"),
        sa.Column("false_positive_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("missed_detection_count", sa.Integer(), nullable=False, server_default="0"),
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
        sa.UniqueConstraint("user_id", name="uq_user_calibration_user_id"),
        sa.CheckConstraint(
            "low_threshold >= 0 AND low_threshold <= 100",
            name="ck_user_calibration_low_range",
        ),
        sa.CheckConstraint(
            "medium_threshold >= 0 AND medium_threshold <= 100",
            name="ck_user_calibration_medium_range",
        ),
        sa.CheckConstraint(
            "high_threshold >= 0 AND high_threshold <= 100",
            name="ck_user_calibration_high_range",
        ),
        sa.CheckConstraint(
            "low_threshold < medium_threshold AND medium_threshold < high_threshold",
            name="ck_user_calibration_threshold_order",
        ),
        sa.CheckConstraint(
            "decay_factor >= 0.0 AND decay_factor <= 1.0",
            name="ck_user_calibration_decay_range",
        ),
        sa.CheckConstraint(
            "false_positive_count >= 0",
            name="ck_user_calibration_fp_count",
        ),
        sa.CheckConstraint(
            "missed_detection_count >= 0",
            name="ck_user_calibration_md_count",
        ),
    )

    # Create index for user_calibration
    op.create_index("idx_user_calibration_user_id", "user_calibration", ["user_id"])


def downgrade() -> None:
    """Drop event_feedback and user_calibration tables."""
    # Drop indexes
    op.drop_index("idx_user_calibration_user_id", table_name="user_calibration")
    op.drop_index("idx_event_feedback_created_at", table_name="event_feedback")
    op.drop_index("idx_event_feedback_type", table_name="event_feedback")
    op.drop_index("idx_event_feedback_event_id", table_name="event_feedback")

    # Drop tables
    op.drop_table("user_calibration")
    op.drop_table("event_feedback")
