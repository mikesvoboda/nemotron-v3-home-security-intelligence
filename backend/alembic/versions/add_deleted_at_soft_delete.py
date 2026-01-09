"""Add deleted_at columns for soft delete support

Revision ID: add_deleted_at_soft_delete
Revises: create_scene_changes_table
Create Date: 2026-01-09 12:30:00.000000

This migration adds deleted_at columns to cameras and events tables to support
soft delete functionality. Soft delete allows marking records as deleted without
physically removing them, preserving referential integrity and enabling data recovery.

The deleted_at column:
- Is NULL for active (non-deleted) records
- Contains a timestamp for soft-deleted records
- Enables filtering deleted records in queries with WHERE deleted_at IS NULL

Related Linear issue: NEM-1997
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_deleted_at_soft_delete"
down_revision: str | Sequence[str] | None = "create_scene_changes_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add deleted_at columns to cameras and events tables.

    Creates:
    - cameras.deleted_at - nullable timestamp for soft delete
    - events.deleted_at - nullable timestamp for soft delete
    - Partial indexes for filtering non-deleted records efficiently
    """
    # Add deleted_at to cameras table
    op.add_column(
        "cameras",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Add deleted_at to events table
    op.add_column(
        "events",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Create partial indexes for efficient queries on non-deleted records
    # These indexes only include rows where deleted_at IS NULL (active records)
    # This makes queries like "SELECT * FROM cameras WHERE deleted_at IS NULL" very fast
    op.create_index(
        "idx_cameras_active",
        "cameras",
        ["id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_events_active",
        "events",
        ["id", "started_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    """Remove deleted_at columns from cameras and events tables."""
    # Drop partial indexes first
    op.drop_index("idx_events_active", table_name="events")
    op.drop_index("idx_cameras_active", table_name="cameras")

    # Drop columns
    op.drop_column("events", "deleted_at")
    op.drop_column("cameras", "deleted_at")
