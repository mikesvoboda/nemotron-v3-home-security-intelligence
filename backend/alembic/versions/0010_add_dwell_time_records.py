"""Add dwell_time_records table for loitering detection.

Revision ID: 0010
Revises: 0009
Create Date: 2026-01-26

This migration creates the dwell_time_records table for tracking object
dwell time within polygon zones. This enables loitering detection by
recording entry/exit times and calculating total presence duration.

The table supports:
- Tracking active dwellers (no exit time)
- Historical dwell time analysis
- Loitering alert tracking
- Zone-based analytics
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create dwell_time_records table with indexes."""
    op.create_table(
        "dwell_time_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("zone_id", sa.Integer(), nullable=False),
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.Column("camera_id", sa.String(), nullable=False),
        sa.Column("object_class", sa.String(50), nullable=False),
        sa.Column(
            "entry_time",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "exit_time",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "total_seconds",
            sa.Float(),
            nullable=False,
            server_default="0.0",
        ),
        sa.Column(
            "triggered_alert",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        # Primary key constraint
        sa.PrimaryKeyConstraint("id"),
        # Foreign key constraints with cascade delete
        sa.ForeignKeyConstraint(
            ["zone_id"],
            ["polygon_zones.id"],
            name="fk_dwell_time_zone_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["camera_id"],
            ["cameras.id"],
            name="fk_dwell_time_camera_id",
            ondelete="CASCADE",
        ),
    )

    # Create indexes for efficient querying
    # Index on zone_id for zone-based queries
    op.create_index("idx_dwell_time_zone", "dwell_time_records", ["zone_id"])

    # Index on camera_id for camera-based queries
    op.create_index("idx_dwell_time_camera", "dwell_time_records", ["camera_id"])

    # Index on track_id for object tracking queries
    op.create_index("idx_dwell_time_track", "dwell_time_records", ["track_id"])

    # Index on entry_time for time-based queries
    op.create_index("idx_dwell_time_entry", "dwell_time_records", ["entry_time"])

    # Composite index for finding active records by zone and track
    op.create_index(
        "idx_dwell_time_zone_track",
        "dwell_time_records",
        ["zone_id", "track_id"],
    )

    # Composite index for finding active dwellers (exit_time IS NULL)
    op.create_index(
        "idx_dwell_time_active",
        "dwell_time_records",
        ["zone_id", "exit_time"],
    )


def downgrade() -> None:
    """Drop dwell_time_records table and its indexes."""
    # Drop indexes first
    op.drop_index("idx_dwell_time_active", table_name="dwell_time_records")
    op.drop_index("idx_dwell_time_zone_track", table_name="dwell_time_records")
    op.drop_index("idx_dwell_time_entry", table_name="dwell_time_records")
    op.drop_index("idx_dwell_time_track", table_name="dwell_time_records")
    op.drop_index("idx_dwell_time_camera", table_name="dwell_time_records")
    op.drop_index("idx_dwell_time_zone", table_name="dwell_time_records")

    # Drop table
    op.drop_table("dwell_time_records")
