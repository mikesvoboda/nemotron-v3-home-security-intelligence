"""Add entity model for re-identification tracking

Revision ID: add_entity_model
Revises: add_detection_search_vector
Create Date: 2026-01-10 10:00:00.000000

This migration creates the entities table for person/object re-identification tracking.
The table stores unique entities (persons, vehicles, animals, etc.) that can be tracked
across multiple cameras over time using embedding vectors.

IMPORTANT: No FK constraint on primary_detection_id
============================================
The primary_detection_id column does NOT have a foreign key constraint to detections.id.
This is intentional because:

1. The detections table is partitioned by detected_at with a composite primary key
   (id, detected_at). PostgreSQL does not support FK constraints that reference only
   part of a composite key on partitioned tables.

2. Referential integrity is enforced at the application level in the Entity model
   via the validate_primary_detection() method.

3. The relationship is optional and used primarily for display purposes (showing
   the best thumbnail for an entity), so strict database-level enforcement is not
   critical.

See docs/decisions/entity-detection-referential-integrity.md
for the full architectural decision record.

Related Linear issue: NEM-2210, NEM-2431
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_entity_model"
down_revision: str | Sequence[str] | None = "add_detection_search_vector"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the entities table and associated indexes.

    Creates:
    - entities table with all required columns
    - B-tree indexes for common query patterns
    - GIN index on metadata JSONB for flexible attribute queries
    - CHECK constraints for entity_type and detection_count

    Note: primary_detection_id has no FK constraint due to detections being a
    partitioned table. See migration docstring and ADR-0012 for details.
    """
    # Create the entities table
    # NOTE: No FK constraint on primary_detection_id because detections is partitioned
    # by detected_at with composite PK (id, detected_at). PostgreSQL doesn't support
    # FK references to partial keys on partitioned tables.
    op.create_table(
        "entities",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "entity_type",
            sa.String(20),
            nullable=False,
            server_default="person",
        ),
        sa.Column("embedding_vector", JSONB, nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "detection_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("entity_metadata", JSONB, nullable=True),
        # No ForeignKeyConstraint here - see migration docstring for explanation
        sa.Column("primary_detection_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        # CHECK constraint for valid entity types
        sa.CheckConstraint(
            "entity_type IN ('person', 'vehicle', 'animal', 'package', 'other')",
            name="ck_entities_entity_type",
        ),
        # CHECK constraint for non-negative detection count
        sa.CheckConstraint(
            "detection_count >= 0",
            name="ck_entities_detection_count",
        ),
    )

    # Create index on primary_detection_id for efficient lookups when joining
    # with detections table (even without FK, we still need efficient queries)
    op.create_index(
        "idx_entities_primary_detection_id",
        "entities",
        ["primary_detection_id"],
        postgresql_where=sa.text("primary_detection_id IS NOT NULL"),
    )

    # Create B-tree indexes for common query patterns
    op.create_index("idx_entities_entity_type", "entities", ["entity_type"])
    op.create_index("idx_entities_first_seen_at", "entities", ["first_seen_at"])
    op.create_index("idx_entities_last_seen_at", "entities", ["last_seen_at"])

    # Composite index for type + time filtering
    op.create_index(
        "idx_entities_type_last_seen",
        "entities",
        ["entity_type", "last_seen_at"],
    )

    # GIN index on entity_metadata for flexible attribute queries
    op.create_index(
        "ix_entities_entity_metadata_gin",
        "entities",
        ["entity_metadata"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"entity_metadata": "jsonb_path_ops"},
    )


def downgrade() -> None:
    """Drop the entities table and associated objects.

    Drops:
    - All indexes on entities table
    - entities table
    """
    # Drop indexes first (in reverse order of creation)
    op.drop_index("ix_entities_entity_metadata_gin", table_name="entities")
    op.drop_index("idx_entities_type_last_seen", table_name="entities")
    op.drop_index("idx_entities_last_seen_at", table_name="entities")
    op.drop_index("idx_entities_first_seen_at", table_name="entities")
    op.drop_index("idx_entities_entity_type", table_name="entities")
    op.drop_index("idx_entities_primary_detection_id", table_name="entities")

    # Drop the table
    op.drop_table("entities")
