"""Fix Camera model timezone columns to TIMESTAMPTZ (idempotent)

Revision ID: fix_camera_tz_idem
Revises: 6b206d6591cb
Create Date: 2026-01-13 12:00:00.000000

This migration ensures Camera model's created_at, last_seen_at, and deleted_at columns
use TIMESTAMP WITH TIME ZONE (TIMESTAMPTZ) as defined in the SQLAlchemy model.

This migration is IDEMPOTENT:
- Checks the current column type before attempting any modification
- Skips columns that are already TIMESTAMPTZ
- Safe to run multiple times without errors

Related Linear issue: NEM-2555
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fix_camera_tz_idem"
down_revision: str | Sequence[str] | None = "6b206d6591cb"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _get_column_type(table_name: str, column_name: str) -> str | None:
    """Get the data type of a column from information_schema.

    Args:
        table_name: Name of the table
        column_name: Name of the column

    Returns:
        The data_type from information_schema, or None if column doesn't exist
    """
    bind = op.get_bind()
    result = bind.execute(
        text(
            """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_name = :table_name
            AND column_name = :column_name
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    )
    row = result.fetchone()
    return row[0] if row else None


def _needs_timezone_conversion(table_name: str, column_name: str) -> bool:
    """Check if a column needs to be converted to TIMESTAMPTZ.

    Args:
        table_name: Name of the table
        column_name: Name of the column

    Returns:
        True if column exists and is 'timestamp without time zone', False otherwise
    """
    column_type = _get_column_type(table_name, column_name)
    if column_type is None:
        # Column doesn't exist, skip
        return False
    # PostgreSQL reports timezone-aware as 'timestamp with time zone'
    # and timezone-naive as 'timestamp without time zone'
    return column_type == "timestamp without time zone"


def upgrade() -> None:
    """Convert Camera datetime columns to TIMESTAMPTZ if needed.

    This upgrade is idempotent - it checks each column's current type
    and only converts those that are still TIMESTAMP (without timezone).
    Existing data is assumed to be UTC.
    """
    # cameras.created_at
    if _needs_timezone_conversion("cameras", "created_at"):
        op.alter_column(
            "cameras",
            "created_at",
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using="created_at AT TIME ZONE 'UTC'",
        )

    # cameras.last_seen_at
    if _needs_timezone_conversion("cameras", "last_seen_at"):
        op.alter_column(
            "cameras",
            "last_seen_at",
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using="last_seen_at AT TIME ZONE 'UTC'",
        )

    # cameras.deleted_at (added by add_deleted_at_soft_delete migration)
    if _needs_timezone_conversion("cameras", "deleted_at"):
        op.alter_column(
            "cameras",
            "deleted_at",
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using="deleted_at AT TIME ZONE 'UTC'",
        )


def downgrade() -> None:
    """Revert Camera datetime columns to TIMESTAMP (without timezone) if needed.

    This downgrade is also idempotent - it only converts columns that are
    currently TIMESTAMPTZ back to TIMESTAMP.
    """

    def _is_timestamptz(table_name: str, column_name: str) -> bool:
        """Check if a column is currently TIMESTAMPTZ."""
        column_type = _get_column_type(table_name, column_name)
        return column_type == "timestamp with time zone"

    # cameras.deleted_at
    if _is_timestamptz("cameras", "deleted_at"):
        op.alter_column(
            "cameras",
            "deleted_at",
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )

    # cameras.last_seen_at
    if _is_timestamptz("cameras", "last_seen_at"):
        op.alter_column(
            "cameras",
            "last_seen_at",
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )

    # cameras.created_at
    if _is_timestamptz("cameras", "created_at"):
        op.alter_column(
            "cameras",
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
