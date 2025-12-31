"""Add clip_path column to events table

Revision ID: add_clip_path
Revises: add_baselines
Create Date: 2025-12-31 12:00:00.000000

This migration adds the clip_path column to the events table.
The column stores the path to generated video clips for events.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_clip_path"
down_revision: str | Sequence[str] | None = "add_baselines"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add clip_path column to events table."""
    op.add_column("events", sa.Column("clip_path", sa.String(), nullable=True))


def downgrade() -> None:
    """Remove clip_path column from events table."""
    op.drop_column("events", "clip_path")
