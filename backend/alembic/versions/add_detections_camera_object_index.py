"""Add composite index on detections for camera_id + object_type filtering

Revision ID: add_detections_camera_object_idx
Revises: add_alerts_dedup_indexes
Create Date: 2026-01-06 10:00:00.000000

This migration adds a composite index on the detections table for (camera_id, object_type)
to optimize queries that filter detections by both camera and object type.

Common query patterns this optimizes:
- Get all 'person' detections for a specific camera
- Get all 'vehicle' detections for a specific camera
- Filter dashboard views by camera and detection type

NEM-1538: Add composite index on detections for camera_id + object_type filtering
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_detections_camera_object_idx"
down_revision: str | Sequence[str] | None = "add_alerts_dedup_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add composite index on detections(camera_id, object_type)."""
    op.create_index(
        "idx_detections_camera_object_type",
        "detections",
        ["camera_id", "object_type"],
        unique=False,
    )


def downgrade() -> None:
    """Remove composite index on detections(camera_id, object_type)."""
    # Use if_exists to handle tables recreated by other migrations (e.g., partitioning)
    op.drop_index("idx_detections_camera_object_type", table_name="detections", if_exists=True)
