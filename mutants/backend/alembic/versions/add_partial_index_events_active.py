"""Add partial index for soft delete on events (deleted_at IS NULL)

Revision ID: add_partial_index_events_active
Revises: add_camera_rtsp_fields
Create Date: 2026-02-01

NEM-5052: This migration adds a partial index on the events table to optimize
queries that filter for active (non-deleted) records.

The partial index only includes rows WHERE deleted_at IS NULL, which:
1. Reduces index size by excluding soft-deleted records
2. Improves query performance for the common case of querying active events
3. Follows PostgreSQL best practices for soft delete patterns

This index is particularly useful for:
- Event list queries that filter out deleted events
- Dashboard queries counting active events
- Any query that uses the soft delete pattern (WHERE deleted_at IS NULL)
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_partial_index_events_active"
down_revision: str | Sequence[str] | None = "add_camera_rtsp_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add partial index for active events (deleted_at IS NULL)."""
    op.create_index(
        "idx_events_active",
        "events",
        ["id"],
        unique=False,
        postgresql_where="deleted_at IS NULL",
    )


def downgrade() -> None:
    """Remove partial index for active events."""
    op.drop_index("idx_events_active", table_name="events")
