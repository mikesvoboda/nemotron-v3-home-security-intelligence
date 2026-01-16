"""Add trust_status field to entities table

Revision ID: add_trust_status_to_entities
Revises: 071128727b6c
Create Date: 2026-01-15 00:00:00.000000

This migration adds a trust_status column to the entities table for classifying
entities as trusted, untrusted, or unknown. This enables differential alert
handling based on entity recognition.

Related Linear issue: NEM-2670
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_trust_status_to_entities"
down_revision: str | Sequence[str] | None = "071128727b6c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add trust_status column and related index/constraint to entities table.

    Creates:
    - trust_status column with default value 'unknown'
    - Index on trust_status for filtering by trust level
    - CHECK constraint for valid trust status values
    """
    # Add trust_status column with default value
    op.add_column(
        "entities",
        sa.Column(
            "trust_status",
            sa.String(20),
            nullable=False,
            server_default="unknown",
        ),
    )

    # Create index for efficient trust status filtering
    op.create_index(
        "idx_entities_trust_status",
        "entities",
        ["trust_status"],
    )

    # Add CHECK constraint for valid trust status values
    op.create_check_constraint(
        "ck_entities_trust_status",
        "entities",
        "trust_status IN ('trusted', 'untrusted', 'unknown')",
    )


def downgrade() -> None:
    """Remove trust_status column and related objects from entities table.

    Drops:
    - CHECK constraint for trust status
    - Index on trust_status
    - trust_status column
    """
    # Drop CHECK constraint first
    op.drop_constraint("ck_entities_trust_status", "entities", type_="check")

    # Drop index
    op.drop_index("idx_entities_trust_status", table_name="entities")

    # Drop column
    op.drop_column("entities", "trust_status")
