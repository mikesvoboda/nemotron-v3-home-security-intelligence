"""add_household_member_and_vehicle_tables

Revision ID: a1b2c3d4e5f6
Revises: e36700c35af6
Create Date: 2026-01-19 12:00:00.000000

This migration adds tables for tracking known household members and vehicles
to reduce false positives in security monitoring. These tables enable Nemotron
to recognize trusted persons and vehicles.

Tables created:
- household_members: Known persons who should not trigger high-risk alerts
- person_embeddings: Re-ID embeddings for matching persons to household members
- registered_vehicles: Known vehicles that should not trigger alerts

NEM-3016: Create HouseholdMember and RegisteredVehicle database models
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = "e36700c35af6"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create household member and vehicle tables."""

    # =========================================================================
    # ENUM TYPES
    # =========================================================================

    # Create enum types for household models
    op.execute(
        "CREATE TYPE member_role_enum AS ENUM ('resident', 'family', 'service_worker', 'frequent_visitor')"
    )
    op.execute("CREATE TYPE trust_level_enum AS ENUM ('full', 'partial', 'monitor')")
    op.execute(
        "CREATE TYPE vehicle_type_enum AS ENUM ('car', 'truck', 'motorcycle', 'suv', 'van', 'other')"
    )

    # =========================================================================
    # HOUSEHOLD MEMBERS TABLE
    # =========================================================================

    op.create_table(
        "household_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "resident",
                "family",
                "service_worker",
                "frequent_visitor",
                name="member_role_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "trusted_level",
            sa.Enum("full", "partial", "monitor", name="trust_level_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("typical_schedule", JSONB(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
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
    )

    # Create indexes for household_members
    op.create_index("idx_household_members_role", "household_members", ["role"])
    op.create_index("idx_household_members_trusted_level", "household_members", ["trusted_level"])
    op.create_index(
        "idx_household_members_role_trust", "household_members", ["role", "trusted_level"]
    )

    # =========================================================================
    # PERSON EMBEDDINGS TABLE
    # =========================================================================

    op.create_table(
        "person_embeddings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("embedding", sa.LargeBinary(), nullable=False),
        sa.Column("source_event_id", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["member_id"], ["household_members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_event_id"], ["events.id"], ondelete="SET NULL"),
    )

    # Create indexes for person_embeddings
    op.create_index("idx_person_embeddings_member_id", "person_embeddings", ["member_id"])
    op.create_index(
        "idx_person_embeddings_source_event_id", "person_embeddings", ["source_event_id"]
    )

    # =========================================================================
    # REGISTERED VEHICLES TABLE
    # =========================================================================

    op.create_table(
        "registered_vehicles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("description", sa.String(200), nullable=False),
        sa.Column("license_plate", sa.String(20), nullable=True),
        sa.Column(
            "vehicle_type",
            sa.Enum(
                "car",
                "truck",
                "motorcycle",
                "suv",
                "van",
                "other",
                name="vehicle_type_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("color", sa.String(50), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("trusted", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("reid_embedding", sa.LargeBinary(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_id"], ["household_members.id"], ondelete="SET NULL"),
    )

    # Create indexes for registered_vehicles
    op.create_index("idx_registered_vehicles_owner_id", "registered_vehicles", ["owner_id"])
    op.create_index(
        "idx_registered_vehicles_license_plate", "registered_vehicles", ["license_plate"]
    )
    op.create_index("idx_registered_vehicles_trusted", "registered_vehicles", ["trusted"])
    op.create_index("idx_registered_vehicles_vehicle_type", "registered_vehicles", ["vehicle_type"])


def downgrade() -> None:
    """Drop household member and vehicle tables."""

    # Drop tables in reverse order of creation (respecting FK dependencies)
    op.drop_table("registered_vehicles")
    op.drop_table("person_embeddings")
    op.drop_table("household_members")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS vehicle_type_enum")
    op.execute("DROP TYPE IF EXISTS trust_level_enum")
    op.execute("DROP TYPE IF EXISTS member_role_enum")
