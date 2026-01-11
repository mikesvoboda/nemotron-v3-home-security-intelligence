"""Add entities table for re-identification tracking

Revision ID: add_entities_table
Revises: add_detection_search_vector
Create Date: 2026-01-10 10:00:00.000000

This migration adds the entities table for tracking unique entities (people, vehicles,
animals) across multiple detections. This enables re-identification by storing
embedding vectors and tracking appearance patterns over time.

Related Linear epic: NEM-1880
Related Linear issue: NEM-2210
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "add_entities_table"
down_revision: str | Sequence[str] | None = "add_detection_search_vector"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create entities table with indexes and constraints."""
    # Create entity_type enum (handle existing enum gracefully)
    # Check if enum exists before creating
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'entity_type_enum')")
    )
    enum_exists = result.scalar()

    if not enum_exists:
        op.execute(
            sa.text(
                "CREATE TYPE entity_type_enum AS ENUM ('person', 'vehicle', 'animal', 'unknown')"
            )
        )

    # Define the enum type for column definition
    entity_type_enum = postgresql.ENUM(
        "person",
        "vehicle",
        "animal",
        "unknown",
        name="entity_type_enum",
        create_type=False,
    )

    # Create entities table
    op.create_table(
        "entities",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "entity_type",
            entity_type_enum,
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "appearance_count",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "embedding_vector",
            postgresql.ARRAY(sa.Float()),
            nullable=True,
        ),
        sa.Column("embedding_model", sa.String(100), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
        # CHECK constraints
        sa.CheckConstraint(
            "appearance_count >= 0",
            name="ck_entities_appearance_count_non_negative",
        ),
        sa.CheckConstraint(
            "first_seen_at <= last_seen_at",
            name="ck_entities_seen_timestamps_order",
        ),
    )

    # Create indexes for common queries
    op.create_index(
        "idx_entities_entity_type",
        "entities",
        ["entity_type"],
    )
    op.create_index(
        "idx_entities_first_seen_at",
        "entities",
        ["first_seen_at"],
    )
    op.create_index(
        "idx_entities_last_seen_at",
        "entities",
        ["last_seen_at"],
    )
    op.create_index(
        "idx_entities_deleted_at",
        "entities",
        ["deleted_at"],
    )
    # Composite index for active entities by type
    op.create_index(
        "idx_entities_type_last_seen",
        "entities",
        ["entity_type", "last_seen_at"],
    )
    # Partial index for active (non-deleted) entities
    op.create_index(
        "idx_entities_active",
        "entities",
        ["id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    # GIN index for JSONB metadata queries
    op.create_index(
        "idx_entities_metadata_gin",
        "entities",
        ["metadata"],
        postgresql_using="gin",
        postgresql_ops={"metadata": "jsonb_path_ops"},
    )


def downgrade() -> None:
    """Drop entities table and enum type."""
    # Drop indexes
    op.drop_index("idx_entities_metadata_gin", table_name="entities", if_exists=True)
    op.drop_index("idx_entities_active", table_name="entities", if_exists=True)
    op.drop_index("idx_entities_type_last_seen", table_name="entities", if_exists=True)
    op.drop_index("idx_entities_deleted_at", table_name="entities", if_exists=True)
    op.drop_index("idx_entities_last_seen_at", table_name="entities", if_exists=True)
    op.drop_index("idx_entities_first_seen_at", table_name="entities", if_exists=True)
    op.drop_index("idx_entities_entity_type", table_name="entities", if_exists=True)

    # Drop table
    op.drop_table("entities")

    # Drop enum type using CASCADE to handle any remaining dependencies
    op.execute(sa.text("DROP TYPE IF EXISTS entity_type_enum CASCADE"))
