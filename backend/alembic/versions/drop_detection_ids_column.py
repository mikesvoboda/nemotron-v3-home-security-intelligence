"""Drop deprecated detection_ids column from events table

Revision ID: drop_detection_ids_column
Revises: add_time_series_partitioning
Create Date: 2026-01-08 12:00:00.000000

This migration removes the deprecated detection_ids TEXT column from the events table.
The column stored detection IDs as a JSON array string (e.g., "[1, 2, 3]"), which is
now replaced by the normalized event_detections junction table (created in
add_event_detections_junction migration).

Prerequisites:
1. The add_event_detections_junction migration must have run successfully
2. All event-detection relationships must be in the event_detections table
3. Application code must use Event.detections relationship instead of detection_ids

Migration Safety:
- This migration verifies that all events with non-empty detection_ids have
  corresponding entries in the event_detections table before dropping the column
- If verification fails, the migration aborts with an error

Rollback Strategy:
- The downgrade recreates the detection_ids column and repopulates it from
  the event_detections junction table
- This ensures safe rollback if issues are discovered after migration

Related Linear issue: NEM-1592
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "drop_detection_ids_column"
down_revision: str | Sequence[str] | None = "add_time_series_partitioning"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop the deprecated detection_ids column after verifying data integrity."""
    conn = op.get_bind()

    # Verification 1: Check that event_detections table exists
    result = conn.execute(
        text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'event_detections'
            )
        """)
    )
    table_exists = result.scalar()
    if not table_exists:
        raise RuntimeError(
            "event_detections table does not exist. "
            "Run add_event_detections_junction migration first."
        )

    # Verification 2: Check that all events with detection_ids have entries in junction table
    # This query finds events that have detection_ids but no corresponding entries in event_detections
    result = conn.execute(
        text("""
            SELECT COUNT(*) FROM events e
            WHERE e.detection_ids IS NOT NULL
              AND e.detection_ids != ''
              AND e.detection_ids != '[]'
              AND NOT EXISTS (
                  SELECT 1 FROM event_detections ed WHERE ed.event_id = e.id
              )
        """)
    )
    orphan_count = result.scalar()

    if orphan_count and orphan_count > 0:
        raise RuntimeError(
            f"Found {orphan_count} events with detection_ids but no entries in event_detections. "
            "Run add_event_detections_junction migration to migrate existing data first."
        )

    # Drop the deprecated column
    # Using IF EXISTS for safety in case column was already dropped
    op.execute(text("ALTER TABLE events DROP COLUMN IF EXISTS detection_ids"))


def downgrade() -> None:
    """Recreate detection_ids column and repopulate from event_detections table."""
    conn = op.get_bind()

    # Check if column already exists (idempotency)
    result = conn.execute(
        text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name = 'events' AND column_name = 'detection_ids'
            )
        """)
    )
    column_exists = result.scalar()

    if not column_exists:
        # Add the detection_ids column back
        op.add_column(
            "events",
            sa.Column("detection_ids", sa.Text(), nullable=True),
        )

    # Repopulate detection_ids from event_detections junction table
    # This uses array_agg to collect detection IDs and json_agg to format as JSON array
    op.execute(
        text("""
            UPDATE events e
            SET detection_ids = (
                SELECT json_agg(ed.detection_id)::text
                FROM event_detections ed
                WHERE ed.event_id = e.id
            )
            WHERE EXISTS (
                SELECT 1 FROM event_detections ed WHERE ed.event_id = e.id
            )
        """)
    )
