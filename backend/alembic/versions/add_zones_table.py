"""Add zones table for camera zone definitions

Revision ID: add_zones_001
Revises: add_alerts_rules
Create Date: 2025-12-28 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_zones_001"
down_revision: str | Sequence[str] | None = "add_alerts_rules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create zones table."""
    # Create zone_type enum
    zone_type_enum = sa.Enum(
        "entry_point", "driveway", "sidewalk", "yard", "other", name="zone_type_enum"
    )
    zone_type_enum.create(op.get_bind(), checkfirst=True)

    # Create zone_shape enum
    zone_shape_enum = sa.Enum("rectangle", "polygon", name="zone_shape_enum")
    zone_shape_enum.create(op.get_bind(), checkfirst=True)

    # Create zones table
    op.create_table(
        "zones",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("camera_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "zone_type",
            sa.Enum("entry_point", "driveway", "sidewalk", "yard", "other", name="zone_type_enum"),
            nullable=False,
        ),
        sa.Column("coordinates", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "shape",
            sa.Enum("rectangle", "polygon", name="zone_shape_enum"),
            nullable=False,
        ),
        sa.Column("color", sa.String(length=7), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes
    op.create_index("idx_zones_camera_id", "zones", ["camera_id"], unique=False)
    op.create_index("idx_zones_enabled", "zones", ["enabled"], unique=False)
    op.create_index("idx_zones_camera_enabled", "zones", ["camera_id", "enabled"], unique=False)


def downgrade() -> None:
    """Drop zones table."""
    # Drop indexes
    op.drop_index("idx_zones_camera_enabled", table_name="zones")
    op.drop_index("idx_zones_enabled", table_name="zones")
    op.drop_index("idx_zones_camera_id", table_name="zones")

    # Drop zones table
    op.drop_table("zones")

    # Drop enums (must be done after table is dropped)
    sa.Enum(name="zone_shape_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="zone_type_enum").drop(op.get_bind(), checkfirst=True)
