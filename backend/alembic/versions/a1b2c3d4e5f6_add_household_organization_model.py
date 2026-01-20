"""add household organization model

Revision ID: a1b2c3d4e5f6
Revises: e36700c35af6
Create Date: 2026-01-20 10:00:00.000000

This migration adds the Household model as the top-level organizational unit
in the system. It allows grouping household members, vehicles, and properties
under a single household entity (e.g., "Svoboda Family").

Changes:
- Creates households table
- Adds household_id foreign key to household_members (nullable)
- Adds household_id foreign key to registered_vehicles (nullable)
- Adds indexes for efficient querying

The foreign keys are nullable initially for backward compatibility with
existing data. A subsequent migration can make them non-nullable after
migrating existing records to a default household.

Implements NEM-3128: Phase 5.1 - Create Household organization model.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = "e36700c35af6"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add households table and household_id FKs to related tables."""

    # =========================================================================
    # CREATE HOUSEHOLDS TABLE
    # =========================================================================
    op.create_table(
        "households",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # =========================================================================
    # ADD HOUSEHOLD_ID FK TO HOUSEHOLD_MEMBERS
    # =========================================================================
    op.add_column(
        "household_members",
        sa.Column("household_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_household_members_household_id",
        "household_members",
        "households",
        ["household_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "idx_household_members_household_id",
        "household_members",
        ["household_id"],
    )

    # =========================================================================
    # ADD HOUSEHOLD_ID FK TO REGISTERED_VEHICLES
    # =========================================================================
    op.add_column(
        "registered_vehicles",
        sa.Column("household_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_registered_vehicles_household_id",
        "registered_vehicles",
        "households",
        ["household_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "idx_registered_vehicles_household_id",
        "registered_vehicles",
        ["household_id"],
    )


def downgrade() -> None:
    """Remove households table and household_id FKs from related tables."""

    # =========================================================================
    # REMOVE HOUSEHOLD_ID FK FROM REGISTERED_VEHICLES
    # =========================================================================
    op.drop_index("idx_registered_vehicles_household_id", table_name="registered_vehicles")
    op.drop_constraint(
        "fk_registered_vehicles_household_id",
        "registered_vehicles",
        type_="foreignkey",
    )
    op.drop_column("registered_vehicles", "household_id")

    # =========================================================================
    # REMOVE HOUSEHOLD_ID FK FROM HOUSEHOLD_MEMBERS
    # =========================================================================
    op.drop_index("idx_household_members_household_id", table_name="household_members")
    op.drop_constraint(
        "fk_household_members_household_id",
        "household_members",
        type_="foreignkey",
    )
    op.drop_column("household_members", "household_id")

    # =========================================================================
    # DROP HOUSEHOLDS TABLE
    # =========================================================================
    op.drop_table("households")
