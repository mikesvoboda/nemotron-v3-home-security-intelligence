"""Add specialized indexes: GIN for JSONB and BRIN for time-series

Revision ID: add_gin_brin_specialized_indexes
Revises: add_gpu_stats_recorded_at_brin, add_partial_indexes_boolean
Create Date: 2026-01-06 13:00:00.000000

This migration adds specialized PostgreSQL indexes to improve query performance:

## GIN Index for JSONB (NEM-1493)

Adds GIN index with jsonb_path_ops on detections.enrichment_data for containment
queries (@>). This enables fast queries like:

```sql
-- Find detections with license plates
SELECT * FROM detections WHERE enrichment_data @> '{"license_plates": [{}]}';

-- Find detections with suspicious clothing
SELECT * FROM detections
WHERE enrichment_data @> '{"clothing_classifications": {"0": {"is_suspicious": true}}}';
```

Using jsonb_path_ops (smaller index, faster containment) vs default GIN:
- Supports @> (containment) operator only
- Does NOT support ? (key existence) operator
- Smaller on disk, faster queries for containment patterns

## BRIN Indexes for Time-Series (NEM-1494)

BRIN (Block Range INdex) indexes are ideal for naturally ordered time-series data:
- ~1000x smaller than B-tree indexes
- Near-zero INSERT overhead
- Excellent for range queries on append-only tables

Tables receiving BRIN indexes on their timestamp columns:
- detections.detected_at (append-only detection records)
- events.started_at (append-only security events)
- logs.timestamp (append-only application logs)
- audit_logs.timestamp (append-only audit trail)

Note: gpu_stats.recorded_at already has BRIN index from a previous migration.
Note: scene_changes.detected_at BRIN index is handled by create_scene_changes_table migration.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_gin_brin_specialized_indexes"
down_revision: str | Sequence[str] | None = (
    "add_gpu_stats_recorded_at_brin",
    "add_partial_indexes_boolean",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add GIN index for JSONB and BRIN indexes for time-series tables."""
    # =========================================================================
    # GIN Index for JSONB enrichment_data (NEM-1493)
    # =========================================================================
    op.create_index(
        "ix_detections_enrichment_data_gin",
        "detections",
        ["enrichment_data"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"enrichment_data": "jsonb_path_ops"},
    )

    # =========================================================================
    # BRIN Indexes for Time-Series Tables (NEM-1494)
    # =========================================================================

    # detections.detected_at - BRIN for time-series queries
    op.create_index(
        "ix_detections_detected_at_brin",
        "detections",
        ["detected_at"],
        unique=False,
        postgresql_using="brin",
    )

    # events.started_at - BRIN for time-series queries
    op.create_index(
        "ix_events_started_at_brin",
        "events",
        ["started_at"],
        unique=False,
        postgresql_using="brin",
    )

    # logs.timestamp - BRIN for time-series queries
    op.create_index(
        "ix_logs_timestamp_brin",
        "logs",
        ["timestamp"],
        unique=False,
        postgresql_using="brin",
    )

    # audit_logs.timestamp - BRIN for time-series queries
    op.create_index(
        "ix_audit_logs_timestamp_brin",
        "audit_logs",
        ["timestamp"],
        unique=False,
        postgresql_using="brin",
    )

    # NOTE: scene_changes.detected_at BRIN index is handled by create_scene_changes_table
    # migration which creates all scene_changes indexes including the BRIN index.


def downgrade() -> None:
    """Remove GIN and BRIN indexes."""
    # Remove BRIN indexes
    # NOTE: ix_scene_changes_detected_at_brin is managed by create_scene_changes_table
    op.drop_index("ix_audit_logs_timestamp_brin", table_name="audit_logs")
    op.drop_index("ix_logs_timestamp_brin", table_name="logs")
    op.drop_index("ix_events_started_at_brin", table_name="events")
    op.drop_index("ix_detections_detected_at_brin", table_name="detections")

    # Remove GIN index
    op.drop_index("ix_detections_enrichment_data_gin", table_name="detections")
