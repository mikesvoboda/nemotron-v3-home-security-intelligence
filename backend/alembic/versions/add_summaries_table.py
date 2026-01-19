"""Add summaries table for LLM-generated narrative summaries

Revision ID: add_summaries_table
Revises: add_extended_gpu_metrics_columns
Create Date: 2026-01-19 03:00:00.000000

This migration creates the summaries table for storing LLM-generated narrative
summaries of security events. Supports both hourly and daily summary types.

Table stores:
- summary_type: 'hourly' or 'daily' (enforced by CHECK constraint)
- content: LLM-generated narrative text
- event_count: Number of high/critical events included
- event_ids: PostgreSQL array of event IDs that were summarized
- window_start/window_end: Time window covered by the summary
- generated_at: When the LLM produced this summary
- created_at: Row creation timestamp

Indexes:
- idx_summaries_type_created: Composite index for fast latest-summary lookups
- idx_summaries_created_at: For cleanup queries (delete old summaries)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_summaries_table"
down_revision: str | Sequence[str] | None = "add_extended_gpu_metrics_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create summaries table."""
    op.create_table(
        "summaries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("summary_type", sa.String(10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False),
        sa.Column("event_ids", postgresql.ARRAY(sa.Integer()), nullable=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        # CHECK constraint to enforce valid summary_type values
        sa.CheckConstraint(
            "summary_type IN ('hourly', 'daily')",
            name="summaries_type_check",
        ),
    )

    # Index for fast latest-summary lookups by type
    op.create_index(
        "idx_summaries_type_created",
        "summaries",
        ["summary_type", sa.text("created_at DESC")],
    )

    # Index for cleanup queries (delete old summaries)
    op.create_index(
        "idx_summaries_created_at",
        "summaries",
        ["created_at"],
    )


def downgrade() -> None:
    """Drop summaries table."""
    op.drop_index("idx_summaries_created_at", "summaries")
    op.drop_index("idx_summaries_type_created", "summaries")
    op.drop_table("summaries")
