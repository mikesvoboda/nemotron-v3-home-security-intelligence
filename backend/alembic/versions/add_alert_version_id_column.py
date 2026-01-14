"""Add version_id column to alerts table for optimistic locking

Revision ID: add_alert_version_id_column
Revises: 6b206d6591cb
Create Date: 2026-01-13 12:00:00.000000

This migration adds the version_id column to the alerts table to support
optimistic locking and prevent race conditions during concurrent
acknowledge/dismiss operations.

The version_id column:
- Is NOT NULL with default value of 1
- Is automatically incremented by SQLAlchemy on each update
- Prevents concurrent modifications by checking version before update
- When a concurrent modification is detected, SQLAlchemy raises StaleDataError

Related Linear issue: NEM-2581
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_alert_version_id_column"
down_revision: str | Sequence[str] | None = "6b206d6591cb"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add version_id column to alerts table for optimistic locking.

    Creates:
    - alerts.version_id - integer column for optimistic locking (default 1)
    """
    op.add_column(
        "alerts",
        sa.Column("version_id", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    """Remove version_id column from alerts table."""
    op.drop_column("alerts", "version_id")
