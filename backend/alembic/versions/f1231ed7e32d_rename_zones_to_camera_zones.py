"""rename zones to camera_zones

Revision ID: f1231ed7e32d
Revises: a1b2c3d4e5f6
Create Date: 2026-01-20 11:37:20.414157

This migration renames the 'zones' table to 'camera_zones' and updates all
related indexes, constraints, and enum types to distinguish detection polygons
from logical Areas in the organizational hierarchy.

Related: NEM-3130, NEM-3113 (Orphaned Infrastructure Integration)
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1231ed7e32d"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Rename zones table to camera_zones with all constraints and indexes."""

    # Step 1: Rename the table
    op.rename_table("zones", "camera_zones")

    # Step 2: Rename indexes
    op.execute("ALTER INDEX idx_zones_camera_id RENAME TO idx_camera_zones_camera_id")
    op.execute("ALTER INDEX idx_zones_enabled RENAME TO idx_camera_zones_enabled")
    op.execute("ALTER INDEX idx_zones_camera_enabled RENAME TO idx_camera_zones_camera_enabled")

    # Step 3: Rename CHECK constraints
    op.execute(
        "ALTER TABLE camera_zones "
        "RENAME CONSTRAINT ck_zones_priority_non_negative "
        "TO ck_camera_zones_priority_non_negative"
    )
    op.execute(
        "ALTER TABLE camera_zones RENAME CONSTRAINT ck_zones_color_hex TO ck_camera_zones_color_hex"
    )

    # Step 4: Rename the enum types to match new naming convention
    op.execute("ALTER TYPE zone_type_enum RENAME TO camera_zone_type_enum")
    op.execute("ALTER TYPE zone_shape_enum RENAME TO camera_zone_shape_enum")


def downgrade() -> None:
    """Revert camera_zones table back to zones with all constraints and indexes."""

    # Step 1: Rename enum types back
    op.execute("ALTER TYPE camera_zone_type_enum RENAME TO zone_type_enum")
    op.execute("ALTER TYPE camera_zone_shape_enum RENAME TO zone_shape_enum")

    # Step 2: Rename CHECK constraints back
    op.execute(
        "ALTER TABLE camera_zones "
        "RENAME CONSTRAINT ck_camera_zones_priority_non_negative "
        "TO ck_zones_priority_non_negative"
    )
    op.execute(
        "ALTER TABLE camera_zones RENAME CONSTRAINT ck_camera_zones_color_hex TO ck_zones_color_hex"
    )

    # Step 3: Rename indexes back
    op.execute("ALTER INDEX idx_camera_zones_camera_id RENAME TO idx_zones_camera_id")
    op.execute("ALTER INDEX idx_camera_zones_enabled RENAME TO idx_zones_enabled")
    op.execute("ALTER INDEX idx_camera_zones_camera_enabled RENAME TO idx_zones_camera_enabled")

    # Step 4: Rename the table back
    op.rename_table("camera_zones", "zones")
