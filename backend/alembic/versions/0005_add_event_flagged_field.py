"""Add flagged field to events table for NEM-3839.

Revision ID: 0005
Revises: 0004
Create Date: 2026-01-26

This migration adds a 'flagged' boolean column to the events table.
The flagged field allows users to mark events for follow-up investigation
directly from the EventDetailModal.

Related Linear issue: NEM-3839 (Wire Up Flag Event and Download Media Buttons)
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add flagged column to events table."""
    op.add_column(
        "events",
        sa.Column(
            "flagged",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Whether event is flagged for follow-up (NEM-3839)",
        ),
    )

    # Add index for filtering flagged events
    op.create_index(
        "ix_events_flagged",
        "events",
        ["flagged"],
        unique=False,
        postgresql_where=sa.text("flagged = true"),
    )


def downgrade() -> None:
    """Remove flagged column from events table."""
    op.drop_index("ix_events_flagged", table_name="events")
    op.drop_column("events", "flagged")
