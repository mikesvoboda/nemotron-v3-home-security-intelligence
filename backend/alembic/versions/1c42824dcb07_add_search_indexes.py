"""Add TSVECTOR indexes for full-text search

Revision ID: 1c42824dcb07
Revises: add_deleted_at_soft_delete
Create Date: 2026-01-09 13:53:14.468173

This migration adds full-text search capabilities to the logs table and
trigram search for detection labels:

1. Logs table:
   - Adds search_vector TSVECTOR column for full-text search on message and component
   - Creates GIN index for fast full-text search
   - Creates trigger to auto-update search_vector on INSERT/UPDATE
   - Backfills existing rows

2. Detections table:
   - Creates GIN trigram index on object_type for efficient LIKE/ILIKE queries
   - Enables pattern matching like '%person%' without full table scans

The pg_trgm extension is already enabled by the add_object_types_gin_trgm migration.

Related Linear issue: NEM-1985
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1c42824dcb07"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = "add_deleted_at_soft_delete"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add TSVECTOR column and indexes for full-text search.

    Adds:
    1. logs.search_vector - TSVECTOR column for full-text search
    2. idx_logs_search_vector - GIN index for fast FTS queries
    3. logs_search_vector_trigger - trigger to auto-update search_vector
    4. idx_detections_object_type_trgm - trigram index for LIKE queries on object_type
    """
    # Ensure pg_trgm extension is available (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ==========================================================================
    # 1. Add TSVECTOR column to logs table
    # ==========================================================================
    op.add_column(
        "logs",
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
    )

    # ==========================================================================
    # 2. Create trigger function to auto-update search_vector on INSERT/UPDATE
    # ==========================================================================
    # The trigger combines: message, component, and level for searchability
    # Weights: A = message (most important), B = component, C = level
    op.execute(
        """
        CREATE OR REPLACE FUNCTION logs_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('english', COALESCE(NEW.message, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.component, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(NEW.level, '')), 'C');
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
        """
    )

    # ==========================================================================
    # 3. Create trigger on logs table
    # ==========================================================================
    op.execute(
        """
        CREATE TRIGGER logs_search_vector_trigger
        BEFORE INSERT OR UPDATE ON logs
        FOR EACH ROW EXECUTE FUNCTION logs_search_vector_update();
        """
    )

    # ==========================================================================
    # 4. Backfill existing logs with search vectors
    # ==========================================================================
    # Batch update to avoid locking the entire table for too long
    op.execute(
        """
        UPDATE logs SET
            search_vector =
                setweight(to_tsvector('english', COALESCE(message, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(component, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(level, '')), 'C')
        WHERE search_vector IS NULL;
        """
    )

    # ==========================================================================
    # 5. Create GIN index on logs.search_vector AFTER backfill
    # ==========================================================================
    # Building index after data population is more efficient
    op.create_index(
        "idx_logs_search_vector",
        "logs",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )

    # ==========================================================================
    # 6. Create GIN trigram index on detections.object_type (if pg_trgm available)
    # ==========================================================================
    # This enables efficient LIKE/ILIKE queries with wildcards on both sides
    # e.g., WHERE object_type ILIKE '%person%'
    # Note: pg_trgm may not be available in all PostgreSQL installations (e.g., Alpine)
    # The CREATE EXTENSION command silently does nothing if the module isn't installed,
    # so we check for the actual operator class in pg_catalog instead of pg_extension
    connection = op.get_bind()
    result = connection.execute(sa.text("SELECT 1 FROM pg_opclass WHERE opcname = 'gin_trgm_ops'"))
    if result.fetchone():
        op.create_index(
            "idx_detections_object_type_trgm",
            "detections",
            ["object_type"],
            unique=False,
            postgresql_using="gin",
            postgresql_ops={"object_type": "gin_trgm_ops"},
        )


def downgrade() -> None:
    """Remove TSVECTOR column and indexes for full-text search."""
    # Drop trigram index on detections (if it exists)
    connection = op.get_bind()
    result = connection.execute(
        sa.text("SELECT 1 FROM pg_indexes WHERE indexname = 'idx_detections_object_type_trgm'")
    )
    if result.fetchone():
        op.drop_index("idx_detections_object_type_trgm", table_name="detections")

    # Drop GIN index on logs.search_vector
    op.drop_index("idx_logs_search_vector", table_name="logs")

    # Drop trigger on logs table
    op.execute("DROP TRIGGER IF EXISTS logs_search_vector_trigger ON logs;")

    # Drop trigger function
    op.execute("DROP FUNCTION IF EXISTS logs_search_vector_update();")

    # Drop search_vector column from logs
    op.drop_column("logs", "search_vector")
