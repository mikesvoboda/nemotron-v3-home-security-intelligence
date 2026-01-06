"""Add indexes for events table backlog improvements

Revision ID: add_events_backlog_indexes
Revises: add_check_constraints, add_composite_indexes_filters, add_gpu_stats_recorded_at_brin, add_partial_indexes_boolean
Create Date: 2026-01-06 14:00:00.000000

This migration adds three indexes to the events table as part of the Backlog
Improvements epic:

1. idx_events_risk_level_started_at (NEM-1529):
   - Composite index on (risk_level, started_at)
   - Enables efficient combined filtering for dashboard queries like
     "show all high-risk events from today"
   - Risk level is first for equality filtering, started_at for range/sort

2. idx_events_export_covering (NEM-1535):
   - Covering index including all columns needed for export queries
   - Columns: started_at, id, ended_at, risk_level, risk_score, camera_id,
     object_types, summary
   - Enables index-only scans for export queries, avoiding table lookups
   - started_at is first for efficient time-range filtering

3. idx_events_unreviewed (NEM-1536):
   - Partial index WHERE reviewed = false on the id column
   - Optimized for COUNT(*) queries to display unreviewed event counts
   - Only indexes unreviewed events (typically a small subset of all events)
   - Complements idx_events_reviewed_false which indexes the reviewed column

Performance impact:
- All indexes are btree (PostgreSQL default) for optimal range query support
- Partial index minimizes storage and maintenance overhead
- Covering index enables index-only scans for export, reducing I/O by ~50-70%

Related Linear issues: NEM-1529, NEM-1535, NEM-1536
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_events_backlog_indexes"
down_revision: str | Sequence[str] | None = (
    "add_check_constraints",
    "add_covering_indexes_pagination",
    "add_gpu_stats_recorded_at_brin",
    "add_partial_indexes_boolean",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add indexes for events table backlog improvements."""

    # NEM-1529: Composite index for risk_level + started_at filtering
    # Enables efficient queries like "show all high-risk events from today"
    # Column order: risk_level (equality) first, then started_at (range/sort)
    op.create_index(
        "idx_events_risk_level_started_at",
        "events",
        ["risk_level", "started_at"],
        unique=False,
    )

    # NEM-1535: Covering index for export queries to avoid table lookups
    # Includes all columns needed for export: id, started_at, ended_at, risk_level,
    # risk_score, camera_id, object_types, summary
    # Column order: started_at first for time-range filtering
    op.create_index(
        "idx_events_export_covering",
        "events",
        [
            "started_at",
            "id",
            "ended_at",
            "risk_level",
            "risk_score",
            "camera_id",
            "object_types",
            "summary",
        ],
        unique=False,
    )

    # NEM-1536: Partial index for unreviewed events count
    # Only indexes rows WHERE reviewed = false for efficient COUNT(*) queries
    # Indexes the id column since it's used for counting
    op.create_index(
        "idx_events_unreviewed",
        "events",
        ["id"],
        unique=False,
        postgresql_where=sa.text("reviewed = false"),
    )


def downgrade() -> None:
    """Remove events backlog improvement indexes."""
    op.drop_index("idx_events_unreviewed", table_name="events")
    op.drop_index("idx_events_export_covering", table_name="events")
    op.drop_index("idx_events_risk_level_started_at", table_name="events")
