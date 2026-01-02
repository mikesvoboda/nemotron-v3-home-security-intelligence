"""Add llm_prompt column to events table

Revision ID: add_llm_prompt
Revises: fix_search_vector_backfill
Create Date: 2026-01-02 12:00:00.000000

This migration adds the llm_prompt column to the events table.
The column stores the full prompt sent to Nemotron LLM for analysis,
enabling debugging and improvement of the AI pipeline.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_llm_prompt"
down_revision: str | Sequence[str] | None = "fix_search_vector_backfill"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add llm_prompt column to events table."""
    op.add_column("events", sa.Column("llm_prompt", sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove llm_prompt column from events table."""
    op.drop_column("events", "llm_prompt")
