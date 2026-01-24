"""add expression indexes, autovacuum settings, and jsonb path indexes

Revision ID: f6g7h8i9j0k1
Revises: e5f6g7h8i9j0
Create Date: 2026-01-23 10:00:00.000000

This migration implements three PostgreSQL optimization tasks:

1. NEM-3391: Add expression indexes for computed columns
   - lower(name) on cameras for case-insensitive lookups
   - date_trunc('hour', detected_at) on detections for hourly aggregations
   - date_trunc('day', started_at) on events for daily aggregations
   - lower(object_type) on detections for case-insensitive object type filtering

2. NEM-3393: Configure per-table autovacuum settings
   - High-write tables (detections, events, logs, gpu_stats, audit_logs)
   - Aggressive autovacuum for tables with high INSERT rates
   - Tuned thresholds and scale factors for production workloads

3. NEM-3420: Add JSONB path extraction indexes
   - GIN indexes with jsonb_path_ops for specific enrichment_data paths
   - Optimized for common query patterns (license plates, faces, violence)
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6g7h8i9j0k1"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = "e5f6g7h8i9j0"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add expression indexes, autovacuum settings, and JSONB path indexes."""

    # =========================================================================
    # NEM-3391: EXPRESSION INDEXES FOR COMPUTED COLUMNS
    # =========================================================================

    # Expression index on lower(name) for case-insensitive camera lookups
    # Enables efficient queries like: WHERE lower(name) = 'front door'
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_cameras_name_lower
        ON cameras (lower(name))
        """
    )

    # Expression index on date_trunc('hour', detected_at) for hourly aggregations
    # Enables efficient queries like: GROUP BY date_trunc('hour', detected_at)
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_detections_detected_at_hourly
        ON detections (date_trunc('hour', detected_at))
        """
    )

    # Expression index on date_trunc('day', started_at) for daily event aggregations
    # Enables efficient queries like: GROUP BY date_trunc('day', started_at)
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_events_started_at_daily
        ON events (date_trunc('day', started_at))
        """
    )

    # Expression index on lower(object_type) for case-insensitive object type filtering
    # Enables efficient queries like: WHERE lower(object_type) = 'person'
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_detections_object_type_lower
        ON detections (lower(object_type))
        WHERE object_type IS NOT NULL
        """
    )

    # Expression index on date_trunc('hour', timestamp) for hourly log aggregations
    # Enables efficient queries for log analytics dashboards
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_logs_timestamp_hourly
        ON logs (date_trunc('hour', timestamp))
        """
    )

    # =========================================================================
    # NEM-3393: PER-TABLE AUTOVACUUM SETTINGS FOR HIGH-WRITE TABLES
    # =========================================================================

    # detections table - Very high INSERT rate (~100+ per minute during active periods)
    # - autovacuum_vacuum_threshold: Start vacuum after 5000 dead tuples
    # - autovacuum_vacuum_scale_factor: Plus 0.01 (1%) of table size
    # - autovacuum_analyze_threshold: Analyze after 2500 inserts
    # - autovacuum_analyze_scale_factor: Plus 0.005 (0.5%) of table size
    # - autovacuum_vacuum_cost_delay: Reduce delay for faster vacuuming
    op.execute(
        """
        ALTER TABLE detections SET (
            autovacuum_vacuum_threshold = 5000,
            autovacuum_vacuum_scale_factor = 0.01,
            autovacuum_analyze_threshold = 2500,
            autovacuum_analyze_scale_factor = 0.005,
            autovacuum_vacuum_cost_delay = 5
        )
        """
    )

    # events table - High INSERT rate, critical for dashboard queries
    # Similar aggressive settings to detections
    op.execute(
        """
        ALTER TABLE events SET (
            autovacuum_vacuum_threshold = 2000,
            autovacuum_vacuum_scale_factor = 0.02,
            autovacuum_analyze_threshold = 1000,
            autovacuum_analyze_scale_factor = 0.01,
            autovacuum_vacuum_cost_delay = 5
        )
        """
    )

    # logs table - Extremely high INSERT rate from all components
    # Most aggressive settings for append-only table
    op.execute(
        """
        ALTER TABLE logs SET (
            autovacuum_vacuum_threshold = 10000,
            autovacuum_vacuum_scale_factor = 0.01,
            autovacuum_analyze_threshold = 5000,
            autovacuum_analyze_scale_factor = 0.005,
            autovacuum_vacuum_cost_delay = 2
        )
        """
    )

    # gpu_stats table - Very high INSERT rate (every 5 seconds per GPU)
    # Time-series data with regular insertions
    op.execute(
        """
        ALTER TABLE gpu_stats SET (
            autovacuum_vacuum_threshold = 5000,
            autovacuum_vacuum_scale_factor = 0.01,
            autovacuum_analyze_threshold = 2500,
            autovacuum_analyze_scale_factor = 0.005,
            autovacuum_vacuum_cost_delay = 5
        )
        """
    )

    # audit_logs table - Moderate INSERT rate but critical for compliance
    op.execute(
        """
        ALTER TABLE audit_logs SET (
            autovacuum_vacuum_threshold = 1000,
            autovacuum_vacuum_scale_factor = 0.05,
            autovacuum_analyze_threshold = 500,
            autovacuum_analyze_scale_factor = 0.02,
            autovacuum_vacuum_cost_delay = 10
        )
        """
    )

    # event_detections junction table - High INSERT rate with events/detections
    op.execute(
        """
        ALTER TABLE event_detections SET (
            autovacuum_vacuum_threshold = 5000,
            autovacuum_vacuum_scale_factor = 0.01,
            autovacuum_analyze_threshold = 2500,
            autovacuum_analyze_scale_factor = 0.005,
            autovacuum_vacuum_cost_delay = 5
        )
        """
    )

    # job_logs table - High INSERT rate during active processing
    op.execute(
        """
        ALTER TABLE job_logs SET (
            autovacuum_vacuum_threshold = 2000,
            autovacuum_vacuum_scale_factor = 0.02,
            autovacuum_analyze_threshold = 1000,
            autovacuum_analyze_scale_factor = 0.01,
            autovacuum_vacuum_cost_delay = 10
        )
        """
    )

    # =========================================================================
    # NEM-3420: JSONB PATH EXTRACTION INDEXES FOR enrichment_data
    # =========================================================================

    # Note: The main GIN index with jsonb_path_ops already exists:
    # ix_detections_enrichment_data_gin for containment queries (@>)
    #
    # These additional indexes optimize specific path extraction queries
    # that are commonly used in the application.

    # Index for extracting license_plates array length
    # Enables efficient queries: WHERE jsonb_array_length(enrichment_data->'license_plates') > 0
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_detections_enrichment_has_license_plates
        ON detections ((enrichment_data ? 'license_plates'))
        WHERE enrichment_data IS NOT NULL
        """
    )

    # Index for extracting faces array existence
    # Enables efficient queries: WHERE enrichment_data ? 'faces'
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_detections_enrichment_has_faces
        ON detections ((enrichment_data ? 'faces'))
        WHERE enrichment_data IS NOT NULL
        """
    )

    # Index for violence detection flag
    # Enables efficient queries for finding detections with violence
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_detections_enrichment_violence
        ON detections (((enrichment_data->'violence_detection'->>'is_violent')::boolean))
        WHERE enrichment_data IS NOT NULL
          AND enrichment_data->'violence_detection' IS NOT NULL
        """
    )

    # Index for image quality score extraction
    # Enables efficient queries: WHERE (enrichment_data->'image_quality'->>'quality_score')::float < 50
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_detections_enrichment_quality_score
        ON detections (((enrichment_data->'image_quality'->>'quality_score')::float))
        WHERE enrichment_data IS NOT NULL
          AND enrichment_data->'image_quality'->'quality_score' IS NOT NULL
        """
    )

    # Composite index for enrichment processing time tracking
    # Enables efficient queries for monitoring enrichment performance
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_detections_enrichment_processing_time
        ON detections (((enrichment_data->>'processing_time_ms')::float))
        WHERE enrichment_data IS NOT NULL
          AND enrichment_data->>'processing_time_ms' IS NOT NULL
        """
    )

    # Index for entities with entity_metadata JSONB
    # Already has ix_entities_entity_metadata_gin, but add path-specific index
    # for common trust_status queries within metadata
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_entities_metadata_trust_score
        ON entities (((entity_metadata->>'trust_score')::float))
        WHERE entity_metadata IS NOT NULL
          AND entity_metadata->>'trust_score' IS NOT NULL
        """
    )


def downgrade() -> None:
    """Remove expression indexes, autovacuum settings, and JSONB path indexes."""

    # =========================================================================
    # REMOVE JSONB PATH EXTRACTION INDEXES
    # =========================================================================
    op.execute("DROP INDEX IF EXISTS ix_entities_metadata_trust_score")
    op.execute("DROP INDEX IF EXISTS ix_detections_enrichment_processing_time")
    op.execute("DROP INDEX IF EXISTS ix_detections_enrichment_quality_score")
    op.execute("DROP INDEX IF EXISTS ix_detections_enrichment_violence")
    op.execute("DROP INDEX IF EXISTS ix_detections_enrichment_has_faces")
    op.execute("DROP INDEX IF EXISTS ix_detections_enrichment_has_license_plates")

    # =========================================================================
    # RESET AUTOVACUUM SETTINGS TO DEFAULTS
    # =========================================================================
    op.execute(
        """
        ALTER TABLE job_logs RESET (
            autovacuum_vacuum_threshold,
            autovacuum_vacuum_scale_factor,
            autovacuum_analyze_threshold,
            autovacuum_analyze_scale_factor,
            autovacuum_vacuum_cost_delay
        )
        """
    )
    op.execute(
        """
        ALTER TABLE event_detections RESET (
            autovacuum_vacuum_threshold,
            autovacuum_vacuum_scale_factor,
            autovacuum_analyze_threshold,
            autovacuum_analyze_scale_factor,
            autovacuum_vacuum_cost_delay
        )
        """
    )
    op.execute(
        """
        ALTER TABLE audit_logs RESET (
            autovacuum_vacuum_threshold,
            autovacuum_vacuum_scale_factor,
            autovacuum_analyze_threshold,
            autovacuum_analyze_scale_factor,
            autovacuum_vacuum_cost_delay
        )
        """
    )
    op.execute(
        """
        ALTER TABLE gpu_stats RESET (
            autovacuum_vacuum_threshold,
            autovacuum_vacuum_scale_factor,
            autovacuum_analyze_threshold,
            autovacuum_analyze_scale_factor,
            autovacuum_vacuum_cost_delay
        )
        """
    )
    op.execute(
        """
        ALTER TABLE logs RESET (
            autovacuum_vacuum_threshold,
            autovacuum_vacuum_scale_factor,
            autovacuum_analyze_threshold,
            autovacuum_analyze_scale_factor,
            autovacuum_vacuum_cost_delay
        )
        """
    )
    op.execute(
        """
        ALTER TABLE events RESET (
            autovacuum_vacuum_threshold,
            autovacuum_vacuum_scale_factor,
            autovacuum_analyze_threshold,
            autovacuum_analyze_scale_factor,
            autovacuum_vacuum_cost_delay
        )
        """
    )
    op.execute(
        """
        ALTER TABLE detections RESET (
            autovacuum_vacuum_threshold,
            autovacuum_vacuum_scale_factor,
            autovacuum_analyze_threshold,
            autovacuum_analyze_scale_factor,
            autovacuum_vacuum_cost_delay
        )
        """
    )

    # =========================================================================
    # REMOVE EXPRESSION INDEXES
    # =========================================================================
    op.execute("DROP INDEX IF EXISTS ix_logs_timestamp_hourly")
    op.execute("DROP INDEX IF EXISTS ix_detections_object_type_lower")
    op.execute("DROP INDEX IF EXISTS ix_events_started_at_daily")
    op.execute("DROP INDEX IF EXISTS ix_detections_detected_at_hourly")
    op.execute("DROP INDEX IF EXISTS ix_cameras_name_lower")
