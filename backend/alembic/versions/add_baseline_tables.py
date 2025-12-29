"""Add baseline tables for anomaly detection

Revision ID: add_baselines
Revises: add_audit_logs
Create Date: 2025-12-28 15:45:00.000000

This migration adds tables for tracking baseline activity patterns:
1. activity_baselines: Per-camera activity rate by hour and day-of-week
2. class_baselines: Per-camera detection class frequency by hour

These tables support anomaly detection by comparing current detections
against historical baseline patterns with exponential decay.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_baselines"
down_revision: str | Sequence[str] | None = "add_audit_logs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create baseline tables for anomaly detection."""
    # Create activity_baselines table
    op.create_table(
        "activity_baselines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("camera_id", sa.String(), nullable=False),
        sa.Column("hour", sa.Integer(), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("avg_count", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["camera_id"],
            ["cameras.id"],
            name="fk_activity_baselines_camera_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create unique constraint and indexes for activity_baselines
    op.create_unique_constraint(
        "uq_activity_baseline_slot",
        "activity_baselines",
        ["camera_id", "hour", "day_of_week"],
    )
    op.create_index(
        "idx_activity_baseline_camera",
        "activity_baselines",
        ["camera_id"],
        unique=False,
    )
    op.create_index(
        "idx_activity_baseline_slot",
        "activity_baselines",
        ["camera_id", "hour", "day_of_week"],
        unique=False,
    )

    # Create class_baselines table
    op.create_table(
        "class_baselines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("camera_id", sa.String(), nullable=False),
        sa.Column("detection_class", sa.String(), nullable=False),
        sa.Column("hour", sa.Integer(), nullable=False),
        sa.Column("frequency", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["camera_id"],
            ["cameras.id"],
            name="fk_class_baselines_camera_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create unique constraint and indexes for class_baselines
    op.create_unique_constraint(
        "uq_class_baseline_slot",
        "class_baselines",
        ["camera_id", "detection_class", "hour"],
    )
    op.create_index(
        "idx_class_baseline_camera",
        "class_baselines",
        ["camera_id"],
        unique=False,
    )
    op.create_index(
        "idx_class_baseline_class",
        "class_baselines",
        ["camera_id", "detection_class"],
        unique=False,
    )
    op.create_index(
        "idx_class_baseline_slot",
        "class_baselines",
        ["camera_id", "detection_class", "hour"],
        unique=False,
    )


def downgrade() -> None:
    """Drop baseline tables."""
    # Drop indexes for class_baselines
    op.drop_index("idx_class_baseline_slot", table_name="class_baselines")
    op.drop_index("idx_class_baseline_class", table_name="class_baselines")
    op.drop_index("idx_class_baseline_camera", table_name="class_baselines")
    op.drop_constraint("uq_class_baseline_slot", "class_baselines", type_="unique")

    # Drop class_baselines table
    op.drop_table("class_baselines")

    # Drop indexes for activity_baselines
    op.drop_index("idx_activity_baseline_slot", table_name="activity_baselines")
    op.drop_index("idx_activity_baseline_camera", table_name="activity_baselines")
    op.drop_constraint("uq_activity_baseline_slot", "activity_baselines", type_="unique")

    # Drop activity_baselines table
    op.drop_table("activity_baselines")
