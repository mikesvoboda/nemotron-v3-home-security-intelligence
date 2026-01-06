"""Add GIN trigram index on events.object_types for LIKE query performance

Revision ID: add_object_types_gin_trgm
Revises: add_enrichment_data
Create Date: 2026-01-03 12:00:00.000000

This migration adds a GIN index using the pg_trgm (trigram) extension to the
events.object_types column. This enables efficient LIKE/ILIKE queries with
leading wildcards (e.g., '%person%', '%,person,%').

The pg_trgm extension breaks text into trigrams (3-character sequences) and
creates a GIN index over them. This allows PostgreSQL to use the index for:
- LIKE '%pattern%' queries (both prefix and suffix wildcards)
- ILIKE '%pattern%' queries (case-insensitive)
- Similarity searches using pg_trgm operators

Without this index, LIKE queries with leading wildcards cause full table scans,
which can be a significant performance issue for security systems with many events.

Context: The object_types column stores comma-separated object types from
detections (e.g., "person,vehicle,dog"). Queries use patterns like:
- Event.object_types.like('%,person,%')
- Event.object_types.ilike('%person%')
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_object_types_gin_trgm"
down_revision: str | Sequence[str] | None = "add_enrichment_data"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add pg_trgm extension and GIN index on events.object_types."""
    # Enable pg_trgm extension (required for trigram indexes)
    # This is idempotent - will not fail if already enabled
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Create GIN index using gin_trgm_ops operator class
    # This enables efficient LIKE/ILIKE queries with wildcards on both sides
    op.create_index(
        "idx_events_object_types_trgm",
        "events",
        ["object_types"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"object_types": "gin_trgm_ops"},
    )


def downgrade() -> None:
    """Remove GIN trigram index on events.object_types.

    Note: We do not drop the pg_trgm extension as it may be used by other
    indexes or queries in the system.
    """
    op.drop_index("idx_events_object_types_trgm", table_name="events")
