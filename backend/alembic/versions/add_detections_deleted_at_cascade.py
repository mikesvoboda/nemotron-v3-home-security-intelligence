"""Add deleted_at column to detections table for cascade soft delete

Revision ID: add_detections_deleted_at_cascade
Revises: add_deleted_at_soft_delete
Create Date: 2026-01-09 15:30:00.000000

This migration adds deleted_at column to detections table to support
cascade soft delete functionality. When a camera or event is soft-deleted,
related detections can also be soft-deleted to maintain data consistency.

Cascade relationships:
- Camera -> Detections: When camera is soft-deleted, detections are soft-deleted
- Event -> Detections: When event is soft-deleted, related detections are soft-deleted

Related Linear issue: NEM-1956
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_detections_deleted_at_cascade"
down_revision: str | Sequence[str] | None = "add_deleted_at_soft_delete"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add deleted_at column to detections table.

    Creates:
    - detections.deleted_at - nullable timestamp for soft delete
    - Partial index for filtering non-deleted records efficiently
    """
    # Add deleted_at to detections table
    op.add_column(
        "detections",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Create partial index for efficient queries on non-deleted records
    # This index only includes rows where deleted_at IS NULL (active records)
    op.create_index(
        "idx_detections_active",
        "detections",
        ["id", "camera_id", "detected_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # Create index for cascade delete queries (finding detections by camera_id)
    op.create_index(
        "idx_detections_camera_deleted",
        "detections",
        ["camera_id", "deleted_at"],
    )


def downgrade() -> None:
    """Remove deleted_at column from detections table."""
    # Drop indexes first
    op.drop_index("idx_detections_camera_deleted", table_name="detections")
    op.drop_index("idx_detections_active", table_name="detections")

    # Drop column
    op.drop_column("detections", "deleted_at")
