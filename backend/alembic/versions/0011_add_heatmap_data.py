"""Add heatmap_data table for movement heatmap visualization.

Revision ID: 0011
Revises: 0010
Create Date: 2026-01-26

This migration creates the heatmap_data table for storing aggregated
movement heatmap data. Heatmaps visualize activity patterns over time
by accumulating detection positions at different resolutions (hourly,
daily, weekly).

The table stores:
- Compressed numpy arrays of detection counts per grid cell
- Time-bucketed aggregations for efficient querying
- Total detection counts for quick statistics
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create heatmap_data table with indexes and constraints."""
    op.create_table(
        "heatmap_data",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("camera_id", sa.String(), nullable=False),
        sa.Column(
            "time_bucket",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Start time of aggregation period (hour/day/week start)",
        ),
        sa.Column(
            "resolution",
            sa.String(20),
            nullable=False,
            comment="Aggregation resolution: hourly, daily, weekly",
        ),
        sa.Column(
            "width",
            sa.Integer(),
            nullable=False,
            comment="Width of heatmap grid in pixels",
        ),
        sa.Column(
            "height",
            sa.Integer(),
            nullable=False,
            comment="Height of heatmap grid in pixels",
        ),
        sa.Column(
            "data",
            sa.LargeBinary(),
            nullable=False,
            comment="Compressed numpy array of detection counts per grid cell",
        ),
        sa.Column(
            "total_detections",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Total detections in this time bucket",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        # Primary key constraint
        sa.PrimaryKeyConstraint("id"),
        # Foreign key constraint with cascade delete
        sa.ForeignKeyConstraint(
            ["camera_id"],
            ["cameras.id"],
            name="fk_heatmap_data_camera_id",
            ondelete="CASCADE",
        ),
        # Check constraints for valid values
        sa.CheckConstraint(
            "resolution IN ('hourly', 'daily', 'weekly')",
            name="ck_heatmap_data_resolution_valid",
        ),
        sa.CheckConstraint(
            "width > 0",
            name="ck_heatmap_data_width_positive",
        ),
        sa.CheckConstraint(
            "height > 0",
            name="ck_heatmap_data_height_positive",
        ),
        sa.CheckConstraint(
            "total_detections >= 0",
            name="ck_heatmap_data_detections_non_negative",
        ),
    )

    # Create indexes for efficient querying
    # Unique index for camera, time bucket, and resolution combination
    op.create_index(
        "ix_heatmap_data_camera_time_resolution",
        "heatmap_data",
        ["camera_id", "time_bucket", "resolution"],
        unique=True,
    )

    # Index for querying by camera and time range
    op.create_index(
        "ix_heatmap_data_camera_time",
        "heatmap_data",
        ["camera_id", "time_bucket"],
    )

    # Index for filtering by resolution
    op.create_index(
        "ix_heatmap_data_resolution",
        "heatmap_data",
        ["resolution"],
    )

    # BRIN index for time-series queries (efficient for chronological data)
    op.create_index(
        "ix_heatmap_data_time_brin",
        "heatmap_data",
        ["time_bucket"],
        postgresql_using="brin",
    )


def downgrade() -> None:
    """Drop heatmap_data table and its indexes."""
    # Drop indexes first
    op.drop_index("ix_heatmap_data_time_brin", table_name="heatmap_data")
    op.drop_index("ix_heatmap_data_resolution", table_name="heatmap_data")
    op.drop_index("ix_heatmap_data_camera_time", table_name="heatmap_data")
    op.drop_index("ix_heatmap_data_camera_time_resolution", table_name="heatmap_data")

    # Drop table
    op.drop_table("heatmap_data")
