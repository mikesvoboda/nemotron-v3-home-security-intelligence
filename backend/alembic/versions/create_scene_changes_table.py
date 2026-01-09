"""Create scene_changes table

Revision ID: create_scene_changes_table
Revises: d896ab921049
Create Date: 2026-01-09 12:00:00.000000

This migration creates the scene_changes table for tracking camera tampering alerts.
The table stores detected visual changes that may indicate camera tampering, angle changes,
or blocked/obscured views. Scene changes are detected by the SceneChangeDetector service
using SSIM (Structural Similarity Index) comparison.

Related Linear issue: NEM-1997
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "create_scene_changes_table"
down_revision: str | Sequence[str] | None = "d896ab921049"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the scene_changes table and associated indexes.

    Creates:
    - scene_changes table with all required columns
    - scene_change_type_enum PostgreSQL enum type
    - B-tree indexes for common query patterns
    - BRIN index on detected_at for time-series queries
    - Partial index on acknowledged=false for dashboard queries
    - CHECK constraint for similarity_score range (0.0 to 1.0)
    """
    # Create the enum type first
    scene_change_type_enum = sa.Enum(
        "view_blocked",
        "angle_changed",
        "view_tampered",
        "unknown",
        name="scene_change_type_enum",
    )
    scene_change_type_enum.create(op.get_bind(), checkfirst=True)

    # Create the scene_changes table
    op.create_table(
        "scene_changes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("camera_id", sa.String(), nullable=False),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "change_type",
            scene_change_type_enum,
            server_default="unknown",
            nullable=False,
        ),
        sa.Column("similarity_score", sa.Float(), nullable=False),
        sa.Column("acknowledged", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("file_path", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["camera_id"],
            ["cameras.id"],
            name="fk_scene_changes_camera_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "similarity_score >= 0.0 AND similarity_score <= 1.0",
            name="ck_scene_changes_similarity_range",
        ),
    )

    # Create B-tree indexes for common query patterns
    op.create_index("idx_scene_changes_camera_id", "scene_changes", ["camera_id"])
    op.create_index("idx_scene_changes_detected_at", "scene_changes", ["detected_at"])
    op.create_index("idx_scene_changes_acknowledged", "scene_changes", ["acknowledged"])
    op.create_index(
        "idx_scene_changes_camera_acknowledged",
        "scene_changes",
        ["camera_id", "acknowledged"],
    )

    # BRIN index for time-series queries on detected_at (append-only chronological data)
    # Much smaller than B-tree (~1000x) and ideal for range queries on ordered timestamps
    op.create_index(
        "ix_scene_changes_detected_at_brin",
        "scene_changes",
        ["detected_at"],
        unique=False,
        postgresql_using="brin",
    )

    # Partial index for unacknowledged scene changes (dashboard queries)
    # Only indexes rows where acknowledged = false for faster dashboard queries
    op.create_index(
        "idx_scene_changes_acknowledged_false",
        "scene_changes",
        ["acknowledged"],
        unique=False,
        postgresql_where=sa.text("acknowledged = false"),
    )


def downgrade() -> None:
    """Drop the scene_changes table and associated objects.

    Drops:
    - All indexes on scene_changes table (B-tree, BRIN, partial)
    - scene_changes table
    - scene_change_type_enum PostgreSQL enum type
    """
    # Drop indexes first (in reverse order of creation)
    op.drop_index("idx_scene_changes_acknowledged_false", table_name="scene_changes")
    op.drop_index("ix_scene_changes_detected_at_brin", table_name="scene_changes")
    op.drop_index("idx_scene_changes_camera_acknowledged", table_name="scene_changes")
    op.drop_index("idx_scene_changes_acknowledged", table_name="scene_changes")
    op.drop_index("idx_scene_changes_detected_at", table_name="scene_changes")
    op.drop_index("idx_scene_changes_camera_id", table_name="scene_changes")

    # Drop the table
    op.drop_table("scene_changes")

    # Drop the enum type
    sa.Enum(name="scene_change_type_enum").drop(op.get_bind(), checkfirst=True)
