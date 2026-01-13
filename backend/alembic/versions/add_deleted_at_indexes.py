"""Add partial indexes on deleted_at columns for soft-delete queries

Revision ID: add_deleted_at_indexes
Revises: fix_camera_tz_idem
Create Date: 2026-01-13 14:00:00.000000

This migration adds partial indexes on deleted_at columns to optimize soft-delete queries.

The existing `add_deleted_at_soft_delete` migration created indexes for active records
(WHERE deleted_at IS NULL). This migration adds complementary indexes for querying
soft-deleted records (WHERE deleted_at IS NOT NULL).

Use cases:
- Viewing deleted items in an admin interface
- Restoring soft-deleted records
- Auditing/compliance queries for deleted data
- Purge operations that target deleted records

Partial indexes are more efficient than full indexes because they only index
the subset of rows matching the WHERE clause.

Related Linear issue: NEM-2598
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_deleted_at_indexes"
down_revision: str | Sequence[str] | None = "fix_camera_tz_idem"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add partial indexes for soft-deleted records.

    Creates partial indexes on deleted_at columns for tables with soft-delete support.
    These indexes only include rows where deleted_at IS NOT NULL (deleted records).
    """
    # Cameras: Index deleted cameras for admin/restoration queries
    op.create_index(
        "ix_cameras_deleted_at",
        "cameras",
        ["deleted_at"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NOT NULL"),
    )

    # Events: Index deleted events for admin/audit queries
    op.create_index(
        "ix_events_deleted_at",
        "events",
        ["deleted_at"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NOT NULL"),
    )


def downgrade() -> None:
    """Remove partial indexes for soft-deleted records."""
    # Use if_exists=True for safety in case indexes don't exist
    op.drop_index("ix_events_deleted_at", table_name="events", if_exists=True)
    op.drop_index("ix_cameras_deleted_at", table_name="cameras", if_exists=True)
