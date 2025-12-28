"""Add full-text search vector to events table

Revision ID: 20251228_fts
Revises: 968b0dff6a9b
Create Date: 2025-12-28 11:39:31.000000

This migration adds PostgreSQL full-text search capability to the events table:
1. Adds object_types column to cache detected object types
2. Adds search_vector TSVECTOR column for full-text search
3. Creates a GIN index on search_vector for efficient searches
4. Creates a trigger function to auto-update search_vector on INSERT/UPDATE
5. Backfills existing events with their search vectors
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20251228_fts"
down_revision: str | Sequence[str] | None = "968b0dff6a9b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add full-text search vector column and trigger to events table."""
    # Add object_types column to cache detected object types
    op.add_column("events", sa.Column("object_types", sa.Text(), nullable=True))

    # Add search_vector column (TSVECTOR type)
    op.add_column(
        "events",
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
    )

    # Create GIN index for efficient full-text search
    op.create_index(
        "idx_events_search_vector",
        "events",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )

    # Create trigger function to auto-update search_vector on INSERT/UPDATE
    # The trigger combines: summary, reasoning, object_types, and camera name (via subquery)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION events_search_vector_update() RETURNS trigger AS $$
        DECLARE
            camera_name_text TEXT;
        BEGIN
            -- Get camera name for this event
            SELECT name INTO camera_name_text
            FROM cameras
            WHERE id = NEW.camera_id;

            -- Update search_vector combining all searchable fields
            NEW.search_vector := to_tsvector('english',
                COALESCE(NEW.summary, '') || ' ' ||
                COALESCE(NEW.reasoning, '') || ' ' ||
                COALESCE(NEW.object_types, '') || ' ' ||
                COALESCE(camera_name_text, '')
            );
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
        """
    )

    # Create trigger on events table
    op.execute(
        """
        CREATE TRIGGER events_search_vector_trigger
        BEFORE INSERT OR UPDATE ON events
        FOR EACH ROW EXECUTE FUNCTION events_search_vector_update();
        """
    )

    # Backfill existing events with search vectors
    # This updates all existing rows, triggering the search vector update
    op.execute(
        """
        UPDATE events SET
            search_vector = to_tsvector('english',
                COALESCE(summary, '') || ' ' ||
                COALESCE(reasoning, '') || ' ' ||
                COALESCE(object_types, '') || ' ' ||
                COALESCE((SELECT name FROM cameras WHERE id = events.camera_id), '')
            );
        """
    )


def downgrade() -> None:
    """Remove full-text search vector column and trigger from events table."""
    # Drop trigger
    op.execute("DROP TRIGGER IF EXISTS events_search_vector_trigger ON events;")

    # Drop trigger function
    op.execute("DROP FUNCTION IF EXISTS events_search_vector_update();")

    # Drop GIN index
    op.drop_index("idx_events_search_vector", table_name="events")

    # Drop search_vector column
    op.drop_column("events", "search_vector")

    # Drop object_types column
    op.drop_column("events", "object_types")
