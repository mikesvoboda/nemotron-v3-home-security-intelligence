"""Add track_id and track_confidence columns to detections table.

Revision ID: 0007
Revises: 0006
Create Date: 2026-01-26

This migration adds object tracking fields to the detections table:

- track_id: Integer identifier for tracking objects across video frames
- track_confidence: Confidence score (0.0-1.0) for the tracking assignment

The track_id field enables multi-object tracking (MOT) capabilities where
the same object detected in consecutive video frames can be linked together.
This supports the BoT-SORT tracker integration for the YOLO26 detection pipeline.

Related feature: Object tracking across video frames for improved event correlation
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add track_id and track_confidence columns to detections table."""
    # Add track_id column for object tracking across frames
    op.add_column(
        "detections",
        sa.Column(
            "track_id",
            sa.Integer(),
            nullable=True,
            comment="Object track identifier for multi-object tracking across frames",
        ),
    )

    # Add track_confidence column for tracking assignment confidence
    op.add_column(
        "detections",
        sa.Column(
            "track_confidence",
            sa.Float(),
            nullable=True,
            comment="Confidence score (0.0-1.0) for the tracking assignment",
        ),
    )

    # Create index on track_id for efficient queries
    # Enables fast lookups like "get all detections for track_id = 42"
    op.create_index(
        "idx_detections_track_id",
        "detections",
        ["track_id"],
        unique=False,
    )

    # Add CHECK constraint for track_confidence range
    # Ensures values are either NULL or within the valid 0.0-1.0 range
    op.create_check_constraint(
        "ck_detections_track_confidence_range",
        "detections",
        sa.text(
            "track_confidence IS NULL OR (track_confidence >= 0.0 AND track_confidence <= 1.0)"
        ),
    )


def downgrade() -> None:
    """Remove track_id and track_confidence columns from detections table."""
    # Drop CHECK constraint first
    op.drop_constraint("ck_detections_track_confidence_range", "detections", type_="check")

    # Drop index before dropping column
    op.drop_index("idx_detections_track_id", table_name="detections")

    # Drop columns
    op.drop_column("detections", "track_confidence")
    op.drop_column("detections", "track_id")
