"""Backfill NULL search_vector values for existing events

Revision ID: fix_search_vector_backfill
Revises: fix_datetime_tz
Create Date: 2026-01-01 19:00:00.000000

This migration fixes events that have NULL search_vector values.

Root cause: The original FTS migration (20251228_fts) created a database trigger
that only fires on INSERT/UPDATE. Events created before the trigger was added,
or events that were never updated after the trigger was created, may have NULL
search_vector values.

This migration backfills all events with NULL search_vector to ensure full-text
search works correctly for all events.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fix_search_vector_backfill"
down_revision: str | Sequence[str] | None = "fix_datetime_tz"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Backfill NULL search_vector values for existing events.

    Uses UPDATE...FROM JOIN pattern to efficiently update all events
    that have NULL search_vector values. The LEFT JOIN ensures events
    are updated even if the camera reference is missing.
    """
    # Backfill events with NULL search_vector
    # Uses LEFT JOIN to handle orphaned events (camera_id reference might be missing)
    op.execute(
        """
        UPDATE events e SET
            search_vector = to_tsvector('english',
                COALESCE(e.summary, '') || ' ' ||
                COALESCE(e.reasoning, '') || ' ' ||
                COALESCE(e.object_types, '') || ' ' ||
                COALESCE(c.name, '')
            )
        FROM cameras c
        WHERE e.camera_id = c.id
          AND e.search_vector IS NULL;
        """
    )

    # Also handle events without a valid camera (orphaned events)
    # These would not be matched by the JOIN above
    op.execute(
        """
        UPDATE events SET
            search_vector = to_tsvector('english',
                COALESCE(summary, '') || ' ' ||
                COALESCE(reasoning, '') || ' ' ||
                COALESCE(object_types, '')
            )
        WHERE search_vector IS NULL
          AND camera_id NOT IN (SELECT id FROM cameras);
        """
    )


def downgrade() -> None:
    """No downgrade needed - backfilling data doesn't need to be undone.

    The search_vector column remains and will continue to work.
    Setting values back to NULL would break search functionality.
    """
    pass
