"""add property and area models

Revision ID: b2c3d4e5f6g7
Revises: f1231ed7e32d
Create Date: 2026-01-20 14:00:00.000000

This migration adds the Property and Area models to support multi-location
household management. It creates the organizational hierarchy:

    Household (org unit)
    └── Properties (locations)
          ├── "Main House"
          │     ├── Areas ("Front Yard", "Garage")
          │     └── Cameras
          └── "Beach House"

Changes:
- Creates properties table
- Creates areas table
- Creates camera_areas association table (many-to-many Camera <-> Area)
- Adds property_id foreign key to cameras (nullable)
- Adds indexes for efficient querying

The property_id FK on cameras is nullable for backward compatibility with
existing camera records that are not yet assigned to a property.

Implements NEM-3129: Phase 5.2 - Create Property and Area models.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6g7"
down_revision: str | Sequence[str] | None = "f1231ed7e32d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add properties, areas, and camera_areas tables; add property_id FK to cameras."""

    # =========================================================================
    # CREATE PROPERTIES TABLE
    # =========================================================================
    op.create_table(
        "properties",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("household_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("timezone", sa.String(50), nullable=False, server_default="UTC"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name="fk_properties_household_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("idx_properties_household_id", "properties", ["household_id"])
    op.create_index("idx_properties_name", "properties", ["name"])

    # =========================================================================
    # CREATE AREAS TABLE
    # =========================================================================
    op.create_table(
        "areas",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("property_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("color", sa.String(7), nullable=False, server_default="#76B900"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["properties.id"],
            name="fk_areas_property_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("idx_areas_property_id", "areas", ["property_id"])
    op.create_index("idx_areas_name", "areas", ["name"])

    # =========================================================================
    # CREATE CAMERA_AREAS ASSOCIATION TABLE (many-to-many Camera <-> Area)
    # =========================================================================
    op.create_table(
        "camera_areas",
        sa.Column("camera_id", sa.String(), nullable=False),
        sa.Column("area_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("camera_id", "area_id"),
        sa.ForeignKeyConstraint(
            ["camera_id"],
            ["cameras.id"],
            name="fk_camera_areas_camera_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["area_id"],
            ["areas.id"],
            name="fk_camera_areas_area_id",
            ondelete="CASCADE",
        ),
    )
    # Add index for efficient lookup by area_id
    op.create_index("idx_camera_areas_area_id", "camera_areas", ["area_id"])

    # =========================================================================
    # ADD PROPERTY_ID FK TO CAMERAS
    # =========================================================================
    op.add_column(
        "cameras",
        sa.Column("property_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_cameras_property_id",
        "cameras",
        "properties",
        ["property_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_cameras_property_id", "cameras", ["property_id"])


def downgrade() -> None:
    """Remove properties, areas, and camera_areas tables; remove property_id FK from cameras."""

    # =========================================================================
    # REMOVE PROPERTY_ID FK FROM CAMERAS
    # =========================================================================
    op.drop_index("idx_cameras_property_id", table_name="cameras")
    op.drop_constraint("fk_cameras_property_id", "cameras", type_="foreignkey")
    op.drop_column("cameras", "property_id")

    # =========================================================================
    # DROP CAMERA_AREAS ASSOCIATION TABLE
    # =========================================================================
    op.drop_index("idx_camera_areas_area_id", table_name="camera_areas")
    op.drop_table("camera_areas")

    # =========================================================================
    # DROP AREAS TABLE
    # =========================================================================
    op.drop_index("idx_areas_name", table_name="areas")
    op.drop_index("idx_areas_property_id", table_name="areas")
    op.drop_table("areas")

    # =========================================================================
    # DROP PROPERTIES TABLE
    # =========================================================================
    op.drop_index("idx_properties_name", table_name="properties")
    op.drop_index("idx_properties_household_id", table_name="properties")
    op.drop_table("properties")
