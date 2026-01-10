"""Add entity model for re-identification tracking

Revision ID: add_entity_model
Revises: add_detection_search_vector
Create Date: 2026-01-10 10:00:00.000000

This migration creates the entities table for person/object re-identification tracking.
The table stores unique entities (persons, vehicles, animals, etc.) that can be tracked
across multiple cameras over time using embedding vectors.

Related Linear issue: NEM-2210
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
    """
    # Create the entities table
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
        sa.Column("primary_detection_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["primary_detection_id"],
            ["detections.id"],
            name="fk_entities_primary_detection_id",
            ondelete="SET NULL",
        ),
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

    # Drop the table
    op.drop_table("entities")
