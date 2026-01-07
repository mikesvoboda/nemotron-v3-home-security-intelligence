"""Add composite index on detections(object_type, detected_at)

Revision ID: add_detections_obj_type_time_idx
Revises: 00c8a000b44f
Create Date: 2026-01-07 00:00:00.000000

This migration adds a composite index on the detections table for class-based
analytics queries. The index enables efficient queries that filter by object
type and then sort or filter by time.

Query patterns optimized by this index:
- "Show all person detections in the last hour"
- "Get vehicle detections ordered by detection time"
- "Count detections by object type within a time range"

Benefits:
- Single index scan for object_type equality + detected_at range queries
- Avoids bitmap intersection that would occur with separate indexes
- Sorted output for pagination without additional sort operation

Column ordering rationale:
- object_type first: equality filter (WHERE object_type = 'person')
- detected_at second: range filter/sort (AND detected_at > '2024-01-01')

Related issues:
- NEM-1591: Add composite index on detections(object_type, detected_at)
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_detections_obj_type_time_idx"
down_revision: str | Sequence[str] | None = "00c8a000b44f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add composite index on detections(object_type, detected_at)."""
    # NEM-1591: Composite index for class-based analytics queries
    # Enables efficient queries like "show all person detections in the last hour"
    # Column order: object_type (equality filter) first, then detected_at (range/sort)
    op.create_index(
        "ix_detections_object_type_detected_at",
        "detections",
        ["object_type", "detected_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove composite index on detections(object_type, detected_at)."""
    op.drop_index("ix_detections_object_type_detected_at", table_name="detections")
