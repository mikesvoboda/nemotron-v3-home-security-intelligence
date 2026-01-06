"""Add event_detections junction table for Event-Detection normalization

Revision ID: add_event_detections_junction
Revises: add_events_backlog_indexes
Create Date: 2026-01-06 15:00:00.000000

This migration normalizes the detection_ids array column in the events table to a
proper junction/association table (event_detections) for better query performance.

Benefits of normalization:
1. Better query performance with proper indexes on foreign keys
2. Referential integrity via foreign key constraints with CASCADE delete
3. Efficient joins for fetching related detections without JSON parsing
4. Support for additional metadata on the relationship (created_at timestamp)
5. Standard SQL patterns for many-to-many relationships

Migration strategy:
1. Create the event_detections junction table with composite primary key
2. Add indexes on event_id, detection_id, and created_at
3. Migrate existing data from events.detection_ids to the junction table
4. Keep the detection_ids column for backward compatibility during transition

Data migration handles both formats:
- JSON array format: "[1, 2, 3]"
- Legacy comma-separated format: "1,2,3"

Related Linear issue: NEM-1495
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_event_detections_junction"
down_revision: str | Sequence[str] | None = "add_events_backlog_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create event_detections junction table and migrate existing data."""

    # 1. Create the junction table with composite primary key
    op.create_table(
        "event_detections",
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("detection_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("event_id", "detection_id"),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["detection_id"],
            ["detections.id"],
            ondelete="CASCADE",
        ),
    )

    # 2. Create indexes for efficient lookups (using IF NOT EXISTS for CI parallelism)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_event_detections_event_id ON event_detections (event_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_event_detections_detection_id ON event_detections (detection_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_event_detections_created_at ON event_detections (created_at)"
    )

    # 3. Migrate existing data from events.detection_ids to junction table
    # This handles both JSON array format "[1, 2, 3]" and legacy CSV format "1,2,3"
    #
    # The migration uses a multi-step approach:
    # a) First try to parse as JSON array (for rows with valid JSON)
    # b) Fall back to comma-separated parsing (for legacy rows)
    # c) Only insert if the detection_id exists in detections table (referential integrity)
    #
    # Using raw SQL for data migration to handle PostgreSQL-specific JSON functions
    op.execute(
        """
        INSERT INTO event_detections (event_id, detection_id, created_at)
        SELECT DISTINCT
            e.id AS event_id,
            d.detection_id::integer AS detection_id,
            e.started_at AS created_at
        FROM events e
        CROSS JOIN LATERAL (
            -- Try JSON array first, fall back to comma-separated
            SELECT unnest(
                CASE
                    -- Valid JSON array: "[1, 2, 3]"
                    WHEN e.detection_ids ~ '^\\s*\\[' AND e.detection_ids ~ '\\]\\s*$'
                    THEN (
                        SELECT array_agg(elem::text)
                        FROM jsonb_array_elements_text(e.detection_ids::jsonb) AS elem
                    )
                    -- Legacy comma-separated: "1,2,3"
                    WHEN e.detection_ids IS NOT NULL AND e.detection_ids != ''
                    THEN string_to_array(replace(e.detection_ids, ' ', ''), ',')
                    ELSE ARRAY[]::text[]
                END
            ) AS detection_id
        ) d
        WHERE e.detection_ids IS NOT NULL
          AND e.detection_ids != ''
          AND e.detection_ids != '[]'
          AND d.detection_id ~ '^[0-9]+$'  -- Ensure it's a valid integer string
          AND EXISTS (
              SELECT 1 FROM detections det WHERE det.id = d.detection_id::integer
          )
        ON CONFLICT (event_id, detection_id) DO NOTHING
        """
    )

    # Note: We keep the detection_ids column for backward compatibility
    # It can be dropped in a future migration after all consumers are updated


def downgrade() -> None:
    """Remove event_detections junction table.

    Note: This does NOT restore data to events.detection_ids.
    If a rollback is needed, the detection_ids column should still contain
    the original data (we didn't remove it in upgrade).
    """
    op.execute("DROP INDEX IF EXISTS idx_event_detections_created_at")
    op.execute("DROP INDEX IF EXISTS idx_event_detections_detection_id")
    op.execute("DROP INDEX IF EXISTS idx_event_detections_event_id")
    op.drop_table("event_detections")
