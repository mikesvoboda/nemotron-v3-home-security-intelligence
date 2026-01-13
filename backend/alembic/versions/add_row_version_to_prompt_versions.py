"""Add row_version column to prompt_versions table for optimistic locking

Revision ID: add_row_version_pv
Revises: 6b206d6591cb
Create Date: 2026-01-13 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_row_version_pv"
down_revision: str | Sequence[str] | None = "6b206d6591cb"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add row_version column to prompt_versions table.

    This column enables optimistic locking to prevent concurrent updates
    from overwriting each other.
    """
    op.add_column(
        "prompt_versions",
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
    )
    # Remove server default after population - the model handles default via Python
    op.alter_column("prompt_versions", "row_version", server_default=None)


def downgrade() -> None:
    """Remove row_version column from prompt_versions table."""
    op.drop_column("prompt_versions", "row_version")
