"""Add unique constraints to cameras table

Revision ID: add_camera_unique_constraints
Revises: add_event_audits
Create Date: 2026-01-02 18:00:00.000000

This migration:
1. Removes duplicate cameras (keeping the oldest one per name or folder_path)
2. Adds unique constraints on 'name' and 'folder_path' columns

The cleanup ensures existing data doesn't violate the new constraints.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_camera_unique_constraints"
down_revision: str | Sequence[str] | None = "add_event_audits"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Clean up duplicate cameras and add unique constraints."""
    # Get database connection for raw SQL operations
    connection = op.get_bind()

    # Step 1: Delete duplicate cameras by name (keep the oldest by created_at)
    # This handles the case where multiple cameras have the same name
    connection.execute(
        sa.text(
            """
            DELETE FROM cameras
            WHERE id IN (
                SELECT id FROM (
                    SELECT id,
                           ROW_NUMBER() OVER (
                               PARTITION BY name
                               ORDER BY created_at ASC, id ASC
                           ) as rn
                    FROM cameras
                ) ranked
                WHERE rn > 1
            )
            """
        )
    )

    # Step 2: Delete duplicate cameras by folder_path (keep the oldest)
    # This handles the case where multiple cameras point to the same folder
    connection.execute(
        sa.text(
            """
            DELETE FROM cameras
            WHERE id IN (
                SELECT id FROM (
                    SELECT id,
                           ROW_NUMBER() OVER (
                               PARTITION BY folder_path
                               ORDER BY created_at ASC, id ASC
                           ) as rn
                    FROM cameras
                ) ranked
                WHERE rn > 1
            )
            """
        )
    )

    # Step 3: Add unique constraint on name
    op.create_index("idx_cameras_name_unique", "cameras", ["name"], unique=True)

    # Step 4: Add unique constraint on folder_path
    op.create_index("idx_cameras_folder_path_unique", "cameras", ["folder_path"], unique=True)


def downgrade() -> None:
    """Remove unique constraints (data cleanup is not reversible)."""
    op.drop_index("idx_cameras_folder_path_unique", table_name="cameras")
    op.drop_index("idx_cameras_name_unique", table_name="cameras")
