"""Add enrichment_data column to detections table

Revision ID: add_enrichment_data
Revises: add_camera_unique_constraints
Create Date: 2026-01-03 12:00:00.000000

This migration adds the enrichment_data JSONB column to the detections table.
The column stores AI enrichment data including:
- Vehicle classification (type, color, damage)
- Pet identification (type, breed)
- Person attributes (clothing, action, carrying)
- License plates (text, confidence)
- Weather conditions
- Image quality scores
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


def downgrade() -> None:
    """Remove enrichment_data column from detections table."""
    op.drop_column("detections", "enrichment_data")
