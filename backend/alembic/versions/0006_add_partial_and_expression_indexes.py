"""Add partial indexes for hot query patterns and JSONB expression indexes.

Revision ID: 0006
Revises: 0005
Create Date: 2026-01-26

This migration adds performance optimizations for frequently-queried columns:

Partial Indexes (NEM-3755):
- idx_detections_high_confidence: Detections with confidence >= 0.8 (high-confidence filtering)
- idx_detections_person_type: Detections where object_type = 'person' (most common query)
- idx_events_high_risk: Events with risk_score >= 60 (high/critical risk monitoring)
- idx_events_active: Events where deleted_at IS NULL (soft-delete filtering)
- idx_events_fast_path: Events where is_fast_path = true (fast path analytics)

JSONB Expression Indexes (NEM-3756):
- idx_detections_has_license_plates: Expression index for license plate presence
- idx_detections_has_faces: Expression index for face detection presence
- idx_events_flags_severity: Expression index on flags->>'severity' for flag filtering

These indexes improve query performance by:
1. Reducing index size (partial indexes only store qualifying rows)
2. Enabling index-only scans for common JSONB field access patterns
3. Supporting efficient filtering on computed/extracted JSONB values
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add partial indexes for hot query patterns and JSONB expression indexes."""

    # =========================================================================
    # PARTIAL INDEXES FOR DETECTIONS (NEM-3755)
    # =========================================================================

    # High-confidence detections (confidence >= 0.8)
    # Optimizes: detection list queries with min_confidence filter
    # Query pattern: WHERE confidence >= 0.8 AND camera_id = X
    op.create_index(
        "idx_detections_high_confidence",
        "detections",
        ["camera_id", "detected_at"],
        unique=False,
        postgresql_where=sa.text("confidence >= 0.8"),
    )

    # Person-type detections (object_type = 'person')
    # Optimizes: Most common object type queries, alert rules, fast path
    # Query pattern: WHERE object_type = 'person' AND detected_at > X
    op.create_index(
        "idx_detections_person_type",
        "detections",
        ["camera_id", "detected_at"],
        unique=False,
        postgresql_where=sa.text("object_type = 'person'"),
    )

    # =========================================================================
    # PARTIAL INDEXES FOR EVENTS (NEM-3755)
    # =========================================================================

    # High-risk events (risk_score >= 60, i.e., high or critical)
    # Optimizes: Dashboard queries for critical/high-risk events
    # Query pattern: WHERE risk_score >= 60 ORDER BY started_at DESC
    op.create_index(
        "idx_events_high_risk",
        "events",
        ["started_at", "camera_id"],
        unique=False,
        postgresql_where=sa.text("risk_score >= 60"),
    )

    # Active (non-deleted) events
    # Optimizes: All queries that filter out soft-deleted events
    # Query pattern: WHERE deleted_at IS NULL ORDER BY started_at DESC
    op.create_index(
        "idx_events_active",
        "events",
        ["started_at", "camera_id"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # Fast-path events
    # Optimizes: Analytics queries for fast-path performance metrics
    # Query pattern: WHERE is_fast_path = true AND started_at BETWEEN X AND Y
    op.create_index(
        "idx_events_fast_path",
        "events",
        ["started_at"],
        unique=False,
        postgresql_where=sa.text("is_fast_path = true"),
    )

    # =========================================================================
    # JSONB EXPRESSION INDEXES FOR DETECTIONS (NEM-3756)
    # =========================================================================

    # Expression index for license plate presence
    # Optimizes: Queries filtering detections that have license plate data
    # Query pattern: WHERE enrichment_data->'license_plates' IS NOT NULL
    #                AND jsonb_array_length(enrichment_data->'license_plates') > 0
    op.execute(
        """
        CREATE INDEX idx_detections_has_license_plates
        ON detections ((enrichment_data->'license_plates' IS NOT NULL
            AND jsonb_array_length(COALESCE(enrichment_data->'license_plates', '[]'::jsonb)) > 0))
        WHERE enrichment_data IS NOT NULL;
        """
    )

    # Expression index for face detection presence
    # Optimizes: Queries filtering detections that have face data
    # Query pattern: WHERE enrichment_data->'faces' IS NOT NULL
    #                AND jsonb_array_length(enrichment_data->'faces') > 0
    op.execute(
        """
        CREATE INDEX idx_detections_has_faces
        ON detections ((enrichment_data->'faces' IS NOT NULL
            AND jsonb_array_length(COALESCE(enrichment_data->'faces', '[]'::jsonb)) > 0))
        WHERE enrichment_data IS NOT NULL;
        """
    )

    # =========================================================================
    # JSONB EXPRESSION INDEXES FOR EVENTS (NEM-3756)
    # =========================================================================

    # Expression index for extracting first flag severity from flags JSONB array
    # Optimizes: Queries that filter events by flag severity
    # Query pattern: WHERE flags->>0->>'severity' = 'critical'
    # Note: Using btree index on extracted text for equality/range lookups
    op.execute(
        """
        CREATE INDEX idx_events_flag_severity
        ON events USING btree ((flags->0->>'severity'))
        WHERE flags IS NOT NULL AND jsonb_array_length(flags) > 0;
        """
    )

    # Expression index for recommended_action lookup
    # Optimizes: Queries that filter events by recommended action
    # Query pattern: WHERE recommended_action = 'monitor' OR recommended_action = 'investigate'
    op.create_index(
        "idx_events_recommended_action",
        "events",
        ["recommended_action"],
        unique=False,
        postgresql_where=sa.text("recommended_action IS NOT NULL"),
    )


def downgrade() -> None:
    """Remove partial indexes and JSONB expression indexes."""

    # Remove JSONB expression indexes for events
    op.drop_index("idx_events_recommended_action", table_name="events")
    op.execute("DROP INDEX IF EXISTS idx_events_flag_severity;")

    # Remove JSONB expression indexes for detections
    op.execute("DROP INDEX IF EXISTS idx_detections_has_faces;")
    op.execute("DROP INDEX IF EXISTS idx_detections_has_license_plates;")

    # Remove partial indexes for events
    op.drop_index("idx_events_fast_path", table_name="events")
    op.drop_index("idx_events_active", table_name="events")
    op.drop_index("idx_events_high_risk", table_name="events")

    # Remove partial indexes for detections
    op.drop_index("idx_detections_person_type", table_name="detections")
    op.drop_index("idx_detections_high_confidence", table_name="detections")
