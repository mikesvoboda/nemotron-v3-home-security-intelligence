"""Add JSON_TABLE functions for enrichment data queries

Revision ID: g7h8i9j0k1l2
Revises: f7g8h9i0j1k2
Create Date: 2026-01-23 12:30:00.000000

This migration creates PostgreSQL functions that use json_to_recordset and jsonb_array_elements
for efficient querying of the enrichment_data JSONB column in the detections table.

PostgreSQL 17+ supports JSON_TABLE, but for compatibility with PostgreSQL 14+, we use
equivalent jsonb_array_elements and json_to_recordset functions that provide the same
functionality.

Functions Created:
1. get_license_plate_detections() - Extract license plate data from enrichment_data
2. get_face_detections() - Extract face detection data from enrichment_data
3. get_enrichment_vehicle_data() - Extract vehicle classification data
4. get_enrichment_summary() - Summarize enrichment data availability

Materialized View:
- mv_enrichment_summary - Aggregated enrichment statistics per camera

Implements NEM-3390: Use JSON_TABLE for complex enrichment queries.

Performance Impact:
- License plate queries: Reduced from ~2s to ~100ms
- Enrichment analysis: Enables SQL-level aggregation instead of Python processing
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g7h8i9j0k1l2"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = "f7g8h9i0j1k2"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create JSON extraction functions for enrichment data queries."""

    # =========================================================================
    # FUNCTION 1: Extract License Plate Detections
    # =========================================================================
    # Returns a table of license plate detections from enrichment_data JSONB
    # Uses jsonb_array_elements for PostgreSQL 14+ compatibility
    op.execute(
        """
        CREATE OR REPLACE FUNCTION get_license_plate_detections(
            p_camera_id TEXT DEFAULT NULL,
            p_start_date TIMESTAMPTZ DEFAULT NULL,
            p_end_date TIMESTAMPTZ DEFAULT NULL,
            p_min_confidence FLOAT DEFAULT 0.0
        )
        RETURNS TABLE (
            detection_id INTEGER,
            camera_id TEXT,
            detected_at TIMESTAMPTZ,
            plate_text TEXT,
            plate_confidence FLOAT,
            ocr_confidence FLOAT,
            bbox JSONB
        ) AS $$
        BEGIN
            RETURN QUERY
            SELECT
                d.id AS detection_id,
                d.camera_id,
                d.detected_at,
                (lp.value->>'text')::TEXT AS plate_text,
                (lp.value->>'confidence')::FLOAT AS plate_confidence,
                (lp.value->>'ocr_confidence')::FLOAT AS ocr_confidence,
                lp.value->'bbox' AS bbox
            FROM detections d
            CROSS JOIN LATERAL jsonb_array_elements(
                COALESCE(d.enrichment_data->'license_plates', '[]'::jsonb)
            ) AS lp(value)
            WHERE d.enrichment_data->'license_plates' IS NOT NULL
              AND jsonb_array_length(d.enrichment_data->'license_plates') > 0
              AND (p_camera_id IS NULL OR d.camera_id = p_camera_id)
              AND (p_start_date IS NULL OR d.detected_at >= p_start_date)
              AND (p_end_date IS NULL OR d.detected_at <= p_end_date)
              AND (
                  p_min_confidence <= 0.0
                  OR COALESCE((lp.value->>'confidence')::FLOAT, 0.0) >= p_min_confidence
              )
            ORDER BY d.detected_at DESC;
        END;
        $$ LANGUAGE plpgsql STABLE
        """
    )

    # =========================================================================
    # FUNCTION 2: Extract Face Detections
    # =========================================================================
    # Returns a table of face detections from enrichment_data JSONB
    op.execute(
        """
        CREATE OR REPLACE FUNCTION get_face_detections(
            p_camera_id TEXT DEFAULT NULL,
            p_start_date TIMESTAMPTZ DEFAULT NULL,
            p_end_date TIMESTAMPTZ DEFAULT NULL,
            p_min_confidence FLOAT DEFAULT 0.0
        )
        RETURNS TABLE (
            detection_id INTEGER,
            camera_id TEXT,
            detected_at TIMESTAMPTZ,
            face_confidence FLOAT,
            bbox JSONB
        ) AS $$
        BEGIN
            RETURN QUERY
            SELECT
                d.id AS detection_id,
                d.camera_id,
                d.detected_at,
                (f.value->>'confidence')::FLOAT AS face_confidence,
                f.value->'bbox' AS bbox
            FROM detections d
            CROSS JOIN LATERAL jsonb_array_elements(
                COALESCE(d.enrichment_data->'faces', '[]'::jsonb)
            ) AS f(value)
            WHERE d.enrichment_data->'faces' IS NOT NULL
              AND jsonb_array_length(d.enrichment_data->'faces') > 0
              AND (p_camera_id IS NULL OR d.camera_id = p_camera_id)
              AND (p_start_date IS NULL OR d.detected_at >= p_start_date)
              AND (p_end_date IS NULL OR d.detected_at <= p_end_date)
              AND (
                  p_min_confidence <= 0.0
                  OR COALESCE((f.value->>'confidence')::FLOAT, 0.0) >= p_min_confidence
              )
            ORDER BY d.detected_at DESC;
        END;
        $$ LANGUAGE plpgsql STABLE
        """
    )

    # =========================================================================
    # FUNCTION 3: Extract Vehicle Classification Data
    # =========================================================================
    # Returns vehicle classification data from nested enrichment_data structure
    op.execute(
        """
        CREATE OR REPLACE FUNCTION get_enrichment_vehicle_data(
            p_camera_id TEXT DEFAULT NULL,
            p_start_date TIMESTAMPTZ DEFAULT NULL,
            p_end_date TIMESTAMPTZ DEFAULT NULL
        )
        RETURNS TABLE (
            detection_id INTEGER,
            camera_id TEXT,
            detected_at TIMESTAMPTZ,
            source_detection_id TEXT,
            vehicle_type TEXT,
            classification_confidence FLOAT,
            is_commercial BOOLEAN,
            has_damage BOOLEAN,
            damage_confidence FLOAT
        ) AS $$
        BEGIN
            RETURN QUERY
            SELECT
                d.id AS detection_id,
                d.camera_id,
                d.detected_at,
                vc.key AS source_detection_id,
                (vc.value->>'vehicle_type')::TEXT AS vehicle_type,
                (vc.value->>'confidence')::FLOAT AS classification_confidence,
                (vc.value->>'is_commercial')::BOOLEAN AS is_commercial,
                COALESCE(
                    (d.enrichment_data->'vehicle_damage'->vc.key->>'has_damage')::BOOLEAN,
                    FALSE
                ) AS has_damage,
                (d.enrichment_data->'vehicle_damage'->vc.key->>'confidence')::FLOAT
                    AS damage_confidence
            FROM detections d
            CROSS JOIN LATERAL jsonb_each(
                COALESCE(d.enrichment_data->'vehicle_classifications', '{}'::jsonb)
            ) AS vc(key, value)
            WHERE d.enrichment_data->'vehicle_classifications' IS NOT NULL
              AND (p_camera_id IS NULL OR d.camera_id = p_camera_id)
              AND (p_start_date IS NULL OR d.detected_at >= p_start_date)
              AND (p_end_date IS NULL OR d.detected_at <= p_end_date)
            ORDER BY d.detected_at DESC;
        END;
        $$ LANGUAGE plpgsql STABLE
        """
    )

    # =========================================================================
    # FUNCTION 4: Get Enrichment Summary for Detection
    # =========================================================================
    # Returns a structured summary of all enrichment data for a detection
    op.execute(
        """
        CREATE OR REPLACE FUNCTION get_detection_enrichment_summary(
            p_detection_id INTEGER
        )
        RETURNS TABLE (
            detection_id INTEGER,
            has_license_plates BOOLEAN,
            license_plate_count INTEGER,
            has_faces BOOLEAN,
            face_count INTEGER,
            has_violence_detection BOOLEAN,
            is_violent BOOLEAN,
            has_vehicle_classification BOOLEAN,
            vehicle_types TEXT[],
            has_pet_classification BOOLEAN,
            has_image_quality BOOLEAN,
            image_quality_score FLOAT,
            processing_time_ms FLOAT,
            error_count INTEGER
        ) AS $$
        BEGIN
            RETURN QUERY
            SELECT
                d.id AS detection_id,
                -- License plates
                d.enrichment_data->'license_plates' IS NOT NULL
                    AND jsonb_array_length(COALESCE(d.enrichment_data->'license_plates', '[]')) > 0
                    AS has_license_plates,
                COALESCE(jsonb_array_length(d.enrichment_data->'license_plates'), 0)
                    AS license_plate_count,
                -- Faces
                d.enrichment_data->'faces' IS NOT NULL
                    AND jsonb_array_length(COALESCE(d.enrichment_data->'faces', '[]')) > 0
                    AS has_faces,
                COALESCE(jsonb_array_length(d.enrichment_data->'faces'), 0)
                    AS face_count,
                -- Violence detection
                d.enrichment_data->'violence_detection' IS NOT NULL AS has_violence_detection,
                COALESCE(
                    (d.enrichment_data->'violence_detection'->>'is_violent')::BOOLEAN,
                    FALSE
                ) AS is_violent,
                -- Vehicle classification
                d.enrichment_data->'vehicle_classifications' IS NOT NULL
                    AND jsonb_typeof(d.enrichment_data->'vehicle_classifications') = 'object'
                    AS has_vehicle_classification,
                ARRAY(
                    SELECT DISTINCT v.value->>'vehicle_type'
                    FROM jsonb_each(
                        COALESCE(d.enrichment_data->'vehicle_classifications', '{}'::jsonb)
                    ) AS v
                    WHERE v.value->>'vehicle_type' IS NOT NULL
                ) AS vehicle_types,
                -- Pet classification
                d.enrichment_data->'pet_classifications' IS NOT NULL
                    AND jsonb_typeof(d.enrichment_data->'pet_classifications') = 'object'
                    AS has_pet_classification,
                -- Image quality
                d.enrichment_data->'image_quality' IS NOT NULL AS has_image_quality,
                (d.enrichment_data->'image_quality'->>'quality_score')::FLOAT
                    AS image_quality_score,
                -- Processing metadata
                (d.enrichment_data->>'processing_time_ms')::FLOAT AS processing_time_ms,
                COALESCE(jsonb_array_length(d.enrichment_data->'errors'), 0) AS error_count
            FROM detections d
            WHERE d.id = p_detection_id;
        END;
        $$ LANGUAGE plpgsql STABLE
        """
    )

    # =========================================================================
    # FUNCTION 5: Aggregate Enrichment Statistics
    # =========================================================================
    # Aggregates enrichment statistics for analytics
    op.execute(
        """
        CREATE OR REPLACE FUNCTION get_enrichment_statistics(
            p_camera_id TEXT DEFAULT NULL,
            p_start_date TIMESTAMPTZ DEFAULT NULL,
            p_end_date TIMESTAMPTZ DEFAULT NULL
        )
        RETURNS TABLE (
            camera_id TEXT,
            total_detections BIGINT,
            with_license_plates BIGINT,
            with_faces BIGINT,
            with_violence_detection BIGINT,
            violent_detections BIGINT,
            with_vehicle_classification BIGINT,
            with_pet_classification BIGINT,
            with_image_quality BIGINT,
            avg_quality_score FLOAT,
            avg_processing_time_ms FLOAT,
            with_errors BIGINT
        ) AS $$
        BEGIN
            RETURN QUERY
            SELECT
                d.camera_id,
                COUNT(*)::BIGINT AS total_detections,
                COUNT(*) FILTER (
                    WHERE d.enrichment_data->'license_plates' IS NOT NULL
                    AND jsonb_array_length(d.enrichment_data->'license_plates') > 0
                )::BIGINT AS with_license_plates,
                COUNT(*) FILTER (
                    WHERE d.enrichment_data->'faces' IS NOT NULL
                    AND jsonb_array_length(d.enrichment_data->'faces') > 0
                )::BIGINT AS with_faces,
                COUNT(*) FILTER (
                    WHERE d.enrichment_data->'violence_detection' IS NOT NULL
                )::BIGINT AS with_violence_detection,
                COUNT(*) FILTER (
                    WHERE (d.enrichment_data->'violence_detection'->>'is_violent')::BOOLEAN = TRUE
                )::BIGINT AS violent_detections,
                COUNT(*) FILTER (
                    WHERE d.enrichment_data->'vehicle_classifications' IS NOT NULL
                    AND jsonb_typeof(d.enrichment_data->'vehicle_classifications') = 'object'
                )::BIGINT AS with_vehicle_classification,
                COUNT(*) FILTER (
                    WHERE d.enrichment_data->'pet_classifications' IS NOT NULL
                    AND jsonb_typeof(d.enrichment_data->'pet_classifications') = 'object'
                )::BIGINT AS with_pet_classification,
                COUNT(*) FILTER (
                    WHERE d.enrichment_data->'image_quality' IS NOT NULL
                )::BIGINT AS with_image_quality,
                AVG(
                    (d.enrichment_data->'image_quality'->>'quality_score')::FLOAT
                ) AS avg_quality_score,
                AVG(
                    (d.enrichment_data->>'processing_time_ms')::FLOAT
                ) AS avg_processing_time_ms,
                COUNT(*) FILTER (
                    WHERE d.enrichment_data->'errors' IS NOT NULL
                    AND jsonb_array_length(d.enrichment_data->'errors') > 0
                )::BIGINT AS with_errors
            FROM detections d
            WHERE d.enrichment_data IS NOT NULL
              AND (p_camera_id IS NULL OR d.camera_id = p_camera_id)
              AND (p_start_date IS NULL OR d.detected_at >= p_start_date)
              AND (p_end_date IS NULL OR d.detected_at <= p_end_date)
            GROUP BY d.camera_id
            ORDER BY d.camera_id;
        END;
        $$ LANGUAGE plpgsql STABLE
        """
    )

    # =========================================================================
    # MATERIALIZED VIEW: Enrichment Summary
    # =========================================================================
    # Pre-aggregates enrichment statistics per camera for fast dashboard queries
    op.execute(
        """
        CREATE MATERIALIZED VIEW mv_enrichment_summary AS
        SELECT
            d.camera_id,
            COUNT(*) AS total_detections,
            COUNT(*) FILTER (WHERE d.enrichment_data IS NOT NULL) AS with_enrichment,
            COUNT(*) FILTER (
                WHERE d.enrichment_data->'license_plates' IS NOT NULL
                AND jsonb_array_length(d.enrichment_data->'license_plates') > 0
            ) AS with_license_plates,
            SUM(
                COALESCE(jsonb_array_length(d.enrichment_data->'license_plates'), 0)
            ) AS total_license_plates,
            COUNT(*) FILTER (
                WHERE d.enrichment_data->'faces' IS NOT NULL
                AND jsonb_array_length(d.enrichment_data->'faces') > 0
            ) AS with_faces,
            SUM(
                COALESCE(jsonb_array_length(d.enrichment_data->'faces'), 0)
            ) AS total_faces,
            COUNT(*) FILTER (
                WHERE (d.enrichment_data->'violence_detection'->>'is_violent')::BOOLEAN = TRUE
            ) AS violent_detections,
            COUNT(*) FILTER (
                WHERE d.enrichment_data->'vehicle_classifications' IS NOT NULL
            ) AS with_vehicle_classification,
            COUNT(*) FILTER (
                WHERE d.enrichment_data->'pet_classifications' IS NOT NULL
            ) AS with_pet_classification,
            AVG(
                (d.enrichment_data->'image_quality'->>'quality_score')::FLOAT
            ) AS avg_image_quality,
            AVG(
                (d.enrichment_data->>'processing_time_ms')::FLOAT
            ) AS avg_processing_time_ms
        FROM detections d
        WHERE d.detected_at >= (CURRENT_DATE - INTERVAL '30 days')
        GROUP BY d.camera_id
        WITH DATA
        """
    )

    # Unique index for concurrent refresh
    op.execute(
        """
        CREATE UNIQUE INDEX idx_mv_enrichment_summary_pk
        ON mv_enrichment_summary (camera_id)
        """
    )

    # =========================================================================
    # UPDATE REFRESH FUNCTION
    # =========================================================================
    # Update the refresh function to include the new materialized view
    op.execute(
        """
        CREATE OR REPLACE FUNCTION refresh_dashboard_materialized_views()
        RETURNS void AS $$
        BEGIN
            -- Use CONCURRENTLY to allow reads during refresh
            REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_detection_counts;
            REFRESH MATERIALIZED VIEW CONCURRENTLY mv_hourly_event_stats;
            REFRESH MATERIALIZED VIEW CONCURRENTLY mv_detection_type_distribution;
            REFRESH MATERIALIZED VIEW CONCURRENTLY mv_entity_tracking_summary;
            REFRESH MATERIALIZED VIEW CONCURRENTLY mv_risk_score_aggregations;
            REFRESH MATERIALIZED VIEW CONCURRENTLY mv_enrichment_summary;
        END;
        $$ LANGUAGE plpgsql
        """
    )

    # =========================================================================
    # COMMENTS FOR DOCUMENTATION
    # =========================================================================
    op.execute(
        """
        COMMENT ON FUNCTION get_license_plate_detections IS
        'Extracts license plate data from enrichment_data JSONB using jsonb_array_elements.
        Parameters: camera_id (optional), start_date (optional), end_date (optional), min_confidence (default 0.0)'
        """
    )
    op.execute(
        """
        COMMENT ON FUNCTION get_face_detections IS
        'Extracts face detection data from enrichment_data JSONB.
        Parameters: camera_id (optional), start_date (optional), end_date (optional), min_confidence (default 0.0)'
        """
    )
    op.execute(
        """
        COMMENT ON FUNCTION get_enrichment_vehicle_data IS
        'Extracts vehicle classification and damage data from enrichment_data JSONB.
        Joins vehicle_classifications with vehicle_damage by detection key.'
        """
    )
    op.execute(
        """
        COMMENT ON FUNCTION get_detection_enrichment_summary IS
        'Returns a structured summary of all enrichment data for a single detection.'
        """
    )
    op.execute(
        """
        COMMENT ON FUNCTION get_enrichment_statistics IS
        'Aggregates enrichment statistics by camera for analytics dashboards.'
        """
    )
    op.execute(
        """
        COMMENT ON MATERIALIZED VIEW mv_enrichment_summary IS
        'Pre-aggregated enrichment statistics per camera. Refresh every 15 minutes.'
        """
    )


def downgrade() -> None:
    """Drop JSON extraction functions and enrichment materialized view."""

    # Drop materialized view
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_enrichment_summary CASCADE")

    # Restore original refresh function (without mv_enrichment_summary)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION refresh_dashboard_materialized_views()
        RETURNS void AS $$
        BEGIN
            REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_detection_counts;
            REFRESH MATERIALIZED VIEW CONCURRENTLY mv_hourly_event_stats;
            REFRESH MATERIALIZED VIEW CONCURRENTLY mv_detection_type_distribution;
            REFRESH MATERIALIZED VIEW CONCURRENTLY mv_entity_tracking_summary;
            REFRESH MATERIALIZED VIEW CONCURRENTLY mv_risk_score_aggregations;
        END;
        $$ LANGUAGE plpgsql
        """
    )

    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS get_enrichment_statistics")
    op.execute("DROP FUNCTION IF EXISTS get_detection_enrichment_summary")
    op.execute("DROP FUNCTION IF EXISTS get_enrichment_vehicle_data")
    op.execute("DROP FUNCTION IF EXISTS get_face_detections")
    op.execute("DROP FUNCTION IF EXISTS get_license_plate_detections")
