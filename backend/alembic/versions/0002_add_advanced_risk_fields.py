"""Add advanced risk analysis fields to events table (NEM-3601).

Revision ID: 0002
Revises: 0001
Create Date: 2026-01-25

This migration adds JSONB columns to the events table for storing
advanced risk analysis data from the Nemotron LLM:

- entities: List of entities identified (people, vehicles, objects)
- flags: Risk flags raised during analysis
- confidence_factors: Factors affecting analysis confidence
- recommended_action: Suggested action based on analysis

These fields capture rich structured data that was previously lost
when Nemotron generated advanced analysis output.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add advanced risk analysis columns to events table."""
    # Add JSONB columns for structured analysis data
    op.add_column(
        "events",
        sa.Column(
            "entities",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Entities identified in analysis (people, vehicles, objects)",
        ),
    )
    op.add_column(
        "events",
        sa.Column(
            "flags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Risk flags raised during analysis",
        ),
    )
    op.add_column(
        "events",
        sa.Column(
            "confidence_factors",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Factors affecting analysis confidence",
        ),
    )
    op.add_column(
        "events",
        sa.Column(
            "recommended_action",
            sa.Text(),
            nullable=True,
            comment="Suggested action based on analysis",
        ),
    )

    # Create GIN indexes for efficient JSONB queries
    # These enable fast containment queries like @> for finding specific entities/flags
    op.create_index(
        "idx_events_entities_gin",
        "events",
        ["entities"],
        postgresql_using="gin",
    )
    op.create_index(
        "idx_events_flags_gin",
        "events",
        ["flags"],
        postgresql_using="gin",
    )
    op.create_index(
        "idx_events_confidence_factors_gin",
        "events",
        ["confidence_factors"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    """Remove advanced risk analysis columns from events table."""
    # Drop indexes first
    op.drop_index("idx_events_confidence_factors_gin", table_name="events")
    op.drop_index("idx_events_flags_gin", table_name="events")
    op.drop_index("idx_events_entities_gin", table_name="events")

    # Drop columns
    op.drop_column("events", "recommended_action")
    op.drop_column("events", "confidence_factors")
    op.drop_column("events", "flags")
    op.drop_column("events", "entities")
