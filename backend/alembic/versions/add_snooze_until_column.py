"""Add snooze_until column to events table for alert snooze

Revision ID: add_snooze_until_column
Revises: add_entity_model
Create Date: 2026-01-11 12:00:00.000000

This migration adds the snooze_until column to the events table to support
alert snooze functionality. When set, alerts for the event are snoozed
until the specified timestamp.

The snooze_until column:
- Is NULL by default (no snooze)
- Contains a timezone-aware timestamp when alerts are snoozed
- When the timestamp is in the past, the snooze is effectively expired

Related Linear issue: NEM-2359
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_snooze_until_column"
down_revision: str | Sequence[str] | None = "add_entity_model"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add snooze_until column to events table.

    Creates:
    - events.snooze_until - nullable timestamp for alert snooze
    """
    op.add_column(
        "events",
        sa.Column("snooze_until", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Remove snooze_until column from events table."""
    op.drop_column("events", "snooze_until")
