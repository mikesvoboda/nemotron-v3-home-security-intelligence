"""add zone activity baselines model

Revision ID: c3d4e5f6g7h9
Revises: c3d4e5f6g7h8
Create Date: 2026-01-21 11:00:00.000000

This migration adds the ZoneActivityBaseline model for storing learned
activity patterns per camera zone. These baselines are used for anomaly
detection.

Changes:
- Creates zone_activity_baselines table
- Adds indexes for efficient querying
- Sets up foreign keys to camera_zones

Implements NEM-3197: Backend Baseline Data Service.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6g7h9"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = "c3d4e5f6g7h8"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create zone_activity_baselines table."""

    # =========================================================================
    # CREATE ZONE_ACTIVITY_BASELINES TABLE
    # =========================================================================
    op.create_table(
        "zone_activity_baselines",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("zone_id", sa.String(), nullable=False),
        sa.Column("camera_id", sa.String(255), nullable=False),
        # Hourly pattern: 24 values (one per hour)
        sa.Column(
            "hourly_pattern",
            postgresql.ARRAY(sa.Float()),
            nullable=False,
            server_default="{}",
        ),
        # Hourly std: 24 values (one per hour)
        sa.Column(
            "hourly_std",
            postgresql.ARRAY(sa.Float()),
            nullable=False,
            server_default="{}",
        ),
        # Daily pattern: 7 values (Monday=0 to Sunday=6)
        sa.Column(
            "daily_pattern",
            postgresql.ARRAY(sa.Float()),
            nullable=False,
            server_default="{}",
        ),
        # Daily std: 7 values
        sa.Column(
            "daily_std",
            postgresql.ARRAY(sa.Float()),
            nullable=False,
            server_default="{}",
        ),
        # Entity class distribution
        sa.Column(
            "entity_class_distribution",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        # Statistical metrics for daily counts
        sa.Column("mean_daily_count", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("std_daily_count", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("min_daily_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_daily_count", sa.Integer(), nullable=False, server_default="0"),
        # Crossing rate statistics
        sa.Column("typical_crossing_rate", sa.Float(), nullable=False, server_default="10.0"),
        sa.Column("typical_crossing_std", sa.Float(), nullable=False, server_default="5.0"),
        # Dwell time statistics
        sa.Column("typical_dwell_time", sa.Float(), nullable=False, server_default="30.0"),
        sa.Column("typical_dwell_std", sa.Float(), nullable=False, server_default="10.0"),
        # Sample info
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        # Primary key
        sa.PrimaryKeyConstraint("id"),
        # Foreign keys
        sa.ForeignKeyConstraint(
            ["zone_id"],
            ["camera_zones.id"],
            name="fk_zone_activity_baselines_zone_id",
            ondelete="CASCADE",
        ),
        # Unique constraint on zone_id (one baseline per zone)
        sa.UniqueConstraint("zone_id", name="uq_zone_activity_baselines_zone_id"),
        # Check constraints
        sa.CheckConstraint("sample_count >= 0", name="ck_baseline_sample_count"),
        sa.CheckConstraint("std_daily_count >= 0", name="ck_baseline_std_daily_count"),
        sa.CheckConstraint("min_daily_count >= 0", name="ck_baseline_min_daily_count"),
        sa.CheckConstraint(
            "max_daily_count >= min_daily_count", name="ck_baseline_max_gte_min_daily"
        ),
        sa.CheckConstraint("typical_crossing_std >= 0", name="ck_baseline_crossing_std"),
        sa.CheckConstraint("typical_dwell_std >= 0", name="ck_baseline_dwell_std"),
    )

    # =========================================================================
    # CREATE INDEXES
    # =========================================================================
    op.create_index(
        "idx_zone_activity_baselines_zone_id",
        "zone_activity_baselines",
        ["zone_id"],
    )
    op.create_index(
        "idx_zone_activity_baselines_camera_id",
        "zone_activity_baselines",
        ["camera_id"],
    )
    op.create_index(
        "idx_zone_activity_baselines_last_updated",
        "zone_activity_baselines",
        ["last_updated"],
    )


def downgrade() -> None:
    """Drop zone_activity_baselines table."""

    # =========================================================================
    # DROP INDEXES
    # =========================================================================
    op.drop_index(
        "idx_zone_activity_baselines_last_updated",
        table_name="zone_activity_baselines",
    )
    op.drop_index(
        "idx_zone_activity_baselines_camera_id",
        table_name="zone_activity_baselines",
    )
    op.drop_index(
        "idx_zone_activity_baselines_zone_id",
        table_name="zone_activity_baselines",
    )

    # =========================================================================
    # DROP TABLE
    # =========================================================================
    op.drop_table("zone_activity_baselines")
