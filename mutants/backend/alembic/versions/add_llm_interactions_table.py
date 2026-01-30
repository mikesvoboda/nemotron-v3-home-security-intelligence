"""Add llm_interactions table for AI pipeline observability (NEM-4234)

Revision ID: add_llm_interactions
Revises: add_alerts_dedup_indexes
Create Date: 2026-01-29 12:00:00.000000

This migration creates the llm_interactions table for capturing what Nemotron
received and responded for debugging accuracy issues in the AI pipeline.

Key fields:
- raw_response: Full LLM output including <think> blocks for reasoning transparency
- enrichment_snapshot: Frozen copy of enrichment_data at analysis time for audit trail
- household_matches: Person/vehicle matches with similarity scores
- truncation_log: What context sections were dropped due to token limits
- context_sources: Which enrichment fields were populated vs empty
- validation_result: Expected vs actual comparison (for synthetic data testing)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_llm_interactions"
down_revision: str | Sequence[str] | None = "add_alerts_dedup_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create llm_interactions table."""
    op.create_table(
        "llm_interactions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("raw_response", sa.Text(), nullable=False),
        sa.Column("enrichment_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("household_matches", postgresql.JSONB(), nullable=True),
        sa.Column("truncation_log", postgresql.JSONB(), nullable=True),
        sa.Column("context_sources", postgresql.JSONB(), nullable=True),
        sa.Column("validation_result", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name="fk_llm_interactions_event_id",
            ondelete="CASCADE",
        ),
    )

    # Create indexes for common queries
    op.create_index(
        "idx_llm_interactions_event_id",
        "llm_interactions",
        ["event_id"],
    )
    op.create_index(
        "idx_llm_interactions_created_at",
        "llm_interactions",
        ["created_at"],
    )


def downgrade() -> None:
    """Drop llm_interactions table."""
    op.drop_index("idx_llm_interactions_created_at", "llm_interactions")
    op.drop_index("idx_llm_interactions_event_id", "llm_interactions")
    op.drop_table("llm_interactions")
