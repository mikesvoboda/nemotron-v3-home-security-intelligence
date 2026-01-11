"""Add enrichment_data JSONB column to detections table

Revision ID: add_enrichment_data
Revises: add_camera_unique_constraints
Create Date: 2026-01-03 10:00:00.000000

This migration adds the enrichment_data JSONB column to the detections table.
The column stores structured results from the 18+ vision models that run
during the enrichment pipeline, enabling queryable access to:
- License plate detection and OCR results
- Face detection results
- Vehicle classification and damage detection
- Clothing analysis (FashionCLIP and SegFormer)
- Violence detection
- Weather classification
- Image quality assessment
- Pet classification
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_enrichment_data"
down_revision: str | Sequence[str] | None = "add_camera_unique_constraints"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add enrichment_data JSONB column to detections table."""
    op.add_column("detections", sa.Column("enrichment_data", JSONB(), nullable=True))

    # Add GIN index for JSONB queries (enables efficient path queries)
    op.create_index(
        "idx_detections_enrichment_data",
        "detections",
        ["enrichment_data"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    """Remove enrichment_data column from detections table."""
    # Use if_exists to handle tables recreated by other migrations (e.g., partitioning)
    op.drop_index("idx_detections_enrichment_data", table_name="detections", if_exists=True)
    op.drop_column("detections", "enrichment_data")
