"""add zone household config model

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-01-21 10:00:00.000000

This migration adds the ZoneHouseholdConfig model for linking camera zones
to household members and vehicles. This enables zone-based access control
and trust management.

Changes:
- Creates zone_household_configs table
- Adds indexes for efficient querying
- Sets up foreign keys to camera_zones and household_members

Implements NEM-3190: Backend Zone-Household Linkage API.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6g7h8"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = "b2c3d4e5f6g7"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create zone_household_configs table."""

    # =========================================================================
    # CREATE ZONE_HOUSEHOLD_CONFIGS TABLE
    # =========================================================================
    op.create_table(
        "zone_household_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("zone_id", sa.String(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column(
            "allowed_member_ids",
            postgresql.ARRAY(sa.Integer()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "allowed_vehicle_ids",
            postgresql.ARRAY(sa.Integer()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "access_schedules",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["zone_id"],
            ["camera_zones.id"],
            name="fk_zone_household_configs_zone_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["household_members.id"],
            name="fk_zone_household_configs_owner_id",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("zone_id", name="uq_zone_household_configs_zone_id"),
    )

    # =========================================================================
    # CREATE INDEXES
    # =========================================================================
    op.create_index(
        "idx_zone_household_configs_owner_id",
        "zone_household_configs",
        ["owner_id"],
    )

    # GIN indexes for array containment queries
    op.create_index(
        "idx_zone_household_configs_allowed_member_ids",
        "zone_household_configs",
        ["allowed_member_ids"],
        postgresql_using="gin",
    )
    op.create_index(
        "idx_zone_household_configs_allowed_vehicle_ids",
        "zone_household_configs",
        ["allowed_vehicle_ids"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    """Drop zone_household_configs table."""

    # =========================================================================
    # DROP INDEXES
    # =========================================================================
    op.drop_index(
        "idx_zone_household_configs_allowed_vehicle_ids",
        table_name="zone_household_configs",
    )
    op.drop_index(
        "idx_zone_household_configs_allowed_member_ids",
        table_name="zone_household_configs",
    )
    op.drop_index(
        "idx_zone_household_configs_owner_id",
        table_name="zone_household_configs",
    )

    # =========================================================================
    # DROP TABLE
    # =========================================================================
    op.drop_table("zone_household_configs")
