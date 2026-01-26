"""Add plate_reads table for ALPR (Automatic License Plate Recognition).

Revision ID: 0014
Revises: 0013
Create Date: 2026-01-26

This migration creates the plate_reads table for storing license plate
recognition results from the ALPR service.

The table stores:
- Recognized plate text and raw OCR output
- Detection and OCR confidence scores
- Bounding box coordinates
- Image quality assessment metrics
- Enhancement and blur flags
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create plate_reads table with indexes and constraints."""
    op.create_table(
        "plate_reads",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("camera_id", sa.String(), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When the plate was detected",
        ),
        sa.Column(
            "plate_text",
            sa.String(20),
            nullable=False,
            comment="Recognized plate text (filtered to alphanumeric)",
        ),
        sa.Column(
            "raw_text",
            sa.String(50),
            nullable=False,
            comment="Original OCR output before filtering",
        ),
        sa.Column(
            "detection_confidence",
            sa.Float(),
            nullable=False,
            comment="Confidence of plate detection/localization (0-1)",
        ),
        sa.Column(
            "ocr_confidence",
            sa.Float(),
            nullable=False,
            comment="Confidence of text recognition (0-1)",
        ),
        sa.Column(
            "bbox",
            JSONB(),
            nullable=False,
            comment="Bounding box coordinates [x1, y1, x2, y2]",
        ),
        sa.Column(
            "image_quality_score",
            sa.Float(),
            nullable=False,
            comment="Quality assessment score (0-1)",
        ),
        sa.Column(
            "is_enhanced",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Whether low-light enhancement was applied",
        ),
        sa.Column(
            "is_blurry",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Whether motion blur was detected",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # Primary key constraint
        sa.PrimaryKeyConstraint("id"),
        # Foreign key constraint with cascade delete
        sa.ForeignKeyConstraint(
            ["camera_id"],
            ["cameras.id"],
            name="fk_plate_reads_camera_id",
            ondelete="CASCADE",
        ),
        # Check constraints for valid values
        sa.CheckConstraint(
            "detection_confidence >= 0 AND detection_confidence <= 1",
            name="ck_plate_reads_detection_confidence_range",
        ),
        sa.CheckConstraint(
            "ocr_confidence >= 0 AND ocr_confidence <= 1",
            name="ck_plate_reads_ocr_confidence_range",
        ),
        sa.CheckConstraint(
            "image_quality_score >= 0 AND image_quality_score <= 1",
            name="ck_plate_reads_quality_score_range",
        ),
    )

    # Create indexes for efficient querying

    # Index on timestamp for time-based queries
    op.create_index(
        "ix_plate_reads_timestamp",
        "plate_reads",
        ["timestamp"],
    )

    # Index on plate_text for text searches
    op.create_index(
        "ix_plate_reads_plate_text",
        "plate_reads",
        ["plate_text"],
    )

    # Composite index for camera + time range queries
    op.create_index(
        "idx_plate_reads_camera_timestamp",
        "plate_reads",
        ["camera_id", "timestamp"],
    )

    # Index on OCR confidence for filtering by confidence
    op.create_index(
        "idx_plate_reads_ocr_confidence",
        "plate_reads",
        ["ocr_confidence"],
    )

    # BRIN index for time-series queries (efficient for chronological data)
    op.create_index(
        "idx_plate_reads_timestamp_brin",
        "plate_reads",
        ["timestamp"],
        postgresql_using="brin",
    )


def downgrade() -> None:
    """Drop plate_reads table and its indexes."""
    # Drop indexes first
    op.drop_index("idx_plate_reads_timestamp_brin", table_name="plate_reads")
    op.drop_index("idx_plate_reads_ocr_confidence", table_name="plate_reads")
    op.drop_index("idx_plate_reads_camera_timestamp", table_name="plate_reads")
    op.drop_index("ix_plate_reads_plate_text", table_name="plate_reads")
    op.drop_index("ix_plate_reads_timestamp", table_name="plate_reads")

    # Drop table
    op.drop_table("plate_reads")
