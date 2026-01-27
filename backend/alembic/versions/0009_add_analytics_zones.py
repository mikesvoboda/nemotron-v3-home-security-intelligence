"""Add line_zones and polygon_zones tables for analytics.

Revision ID: 0009
Revises: 0008
Create Date: 2026-01-26

This migration creates tables for analytics zone detection using the
supervision library integration:

- line_zones: Virtual tripwire detection for counting entries/exits
- polygon_zones: Region-based intrusion detection and object counting

These zones support camera-specific analytics configurations for
automated security monitoring and event correlation.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create line_zones and polygon_zones tables with indexes."""
    # Create the line_zones table
    op.create_table(
        "line_zones",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("camera_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("start_x", sa.Integer(), nullable=False),
        sa.Column("start_y", sa.Integer(), nullable=False),
        sa.Column("end_x", sa.Integer(), nullable=False),
        sa.Column("end_y", sa.Integer(), nullable=False),
        sa.Column("in_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("out_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("alert_on_cross", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "target_classes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default='["person"]',
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["camera_id"],
            ["cameras.id"],
            name="fk_line_zones_camera_id",
            ondelete="CASCADE",
        ),
        # Check constraints for non-negative coordinates
        sa.CheckConstraint("start_x >= 0", name="ck_line_zones_start_x_non_negative"),
        sa.CheckConstraint("start_y >= 0", name="ck_line_zones_start_y_non_negative"),
        sa.CheckConstraint("end_x >= 0", name="ck_line_zones_end_x_non_negative"),
        sa.CheckConstraint("end_y >= 0", name="ck_line_zones_end_y_non_negative"),
        # Check constraints for non-negative counts
        sa.CheckConstraint("in_count >= 0", name="ck_line_zones_in_count_non_negative"),
        sa.CheckConstraint("out_count >= 0", name="ck_line_zones_out_count_non_negative"),
    )

    # Create index for line_zones
    op.create_index("idx_line_zones_camera", "line_zones", ["camera_id"])

    # Create the polygon_zones table
    op.create_table(
        "polygon_zones",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("camera_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "polygon",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("zone_type", sa.String(50), nullable=False, server_default="monitored"),
        sa.Column("alert_threshold", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "target_classes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default='["person"]',
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("color", sa.String(7), nullable=False, server_default="'#FF0000'"),
        sa.Column("current_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["camera_id"],
            ["cameras.id"],
            name="fk_polygon_zones_camera_id",
            ondelete="CASCADE",
        ),
        # Check constraints for non-negative values
        sa.CheckConstraint("alert_threshold >= 0", name="ck_polygon_zones_threshold_non_negative"),
        sa.CheckConstraint("current_count >= 0", name="ck_polygon_zones_count_non_negative"),
        # Validate hex color format
        sa.CheckConstraint("color ~ '^#[0-9A-Fa-f]{6}$'", name="ck_polygon_zones_color_hex"),
        # Validate zone_type enum-like values
        sa.CheckConstraint(
            "zone_type IN ('monitored', 'excluded', 'restricted')",
            name="ck_polygon_zones_type_valid",
        ),
    )

    # Create indexes for polygon_zones
    op.create_index("idx_polygon_zones_camera", "polygon_zones", ["camera_id"])
    op.create_index("idx_polygon_zones_type", "polygon_zones", ["zone_type"])
    op.create_index("idx_polygon_zones_active", "polygon_zones", ["is_active"])


def downgrade() -> None:
    """Drop line_zones and polygon_zones tables and their indexes."""
    # Drop polygon_zones indexes first
    op.drop_index("idx_polygon_zones_active", table_name="polygon_zones")
    op.drop_index("idx_polygon_zones_type", table_name="polygon_zones")
    op.drop_index("idx_polygon_zones_camera", table_name="polygon_zones")

    # Drop polygon_zones table
    op.drop_table("polygon_zones")

    # Drop line_zones index
    op.drop_index("idx_line_zones_camera", table_name="line_zones")

    # Drop line_zones table
    op.drop_table("line_zones")
