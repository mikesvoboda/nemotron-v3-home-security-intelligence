"""Add BRIN index on gpu_stats.recorded_at for time-series optimization

Revision ID: add_gpu_stats_recorded_at_brin
Revises: add_detections_camera_object_idx
Create Date: 2026-01-06 10:00:01.000000

This migration adds a BRIN (Block Range INdex) index on the gpu_stats.recorded_at column
to optimize time-series queries on GPU statistics data.

BRIN indexes are highly efficient for naturally ordered time-series data because:
- They store summary information about ranges of physical table blocks
- Much smaller on disk than B-tree indexes (typically 1000x smaller)
- Ideal when data is inserted in roughly chronological order
- GPU stats are always inserted with monotonically increasing timestamps

Common query patterns this optimizes:
- Get GPU stats for the last hour/day/week
- Time-range filtering for performance dashboards
- Aggregation queries over time windows

Note: This migration replaces the existing B-tree index with a BRIN index for better
performance on time-series data patterns.

NEM-1541: Add index on gpu_stats.recorded_at with BRIN for time-series optimization
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_gpu_stats_recorded_at_brin"
down_revision: str | Sequence[str] | None = "add_detections_camera_object_idx"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add BRIN index on gpu_stats.recorded_at, replacing the existing B-tree index."""
    # Drop the existing B-tree index first
    # Use if_exists to handle tables recreated by other migrations (e.g., partitioning)
    op.drop_index("idx_gpu_stats_recorded_at", table_name="gpu_stats", if_exists=True)

    # Create BRIN index for time-series optimization
    op.create_index(
        "ix_gpu_stats_recorded_at_brin",
        "gpu_stats",
        ["recorded_at"],
        unique=False,
        postgresql_using="brin",
    )


def downgrade() -> None:
    """Restore the B-tree index on gpu_stats.recorded_at."""
    # Drop the BRIN index
    # Use if_exists to handle tables recreated by other migrations (e.g., partitioning)
    op.drop_index("ix_gpu_stats_recorded_at_brin", table_name="gpu_stats", if_exists=True)

    # Restore the original B-tree index
    # Check if it already exists (may have been recreated by partition downgrade)
    from sqlalchemy import inspect

    bind = op.get_bind()
    inspector = inspect(bind)
    indexes = {idx["name"] for idx in inspector.get_indexes("gpu_stats")}

    if "idx_gpu_stats_recorded_at" not in indexes:
        op.create_index(
            "idx_gpu_stats_recorded_at",
            "gpu_stats",
            ["recorded_at"],
            unique=False,
        )
