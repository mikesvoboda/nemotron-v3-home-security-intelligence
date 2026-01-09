"""Add full-text search vector to detections table

Revision ID: add_detection_search_vector
Revises: add_deleted_at_soft_delete
Create Date: 2026-01-09 16:00:00.000000

This migration adds PostgreSQL full-text search capability to the detections table.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "add_detection_search_vector"
down_revision: str | Sequence[str] | None = "add_deleted_at_soft_delete"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add full-text search vector column and trigger to detections table."""
    op.add_column(
        "detections",
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
    )
    op.add_column(
        "detections",
        sa.Column("labels", postgresql.JSONB(), nullable=True),
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION detections_search_vector_update() RETURNS trigger AS $$
        DECLARE
            camera_name_text TEXT;
            enrichment_text TEXT := '';
            labels_array JSONB := '[]'::jsonb;
        BEGIN
            SELECT name INTO camera_name_text FROM cameras WHERE id = NEW.camera_id;

            IF NEW.enrichment_data IS NOT NULL THEN
                IF NEW.enrichment_data ? 'vehicle_classification' THEN
                    enrichment_text := enrichment_text || ' ' ||
                        COALESCE(NEW.enrichment_data->'vehicle_classification'->>'make', '') || ' ' ||
                        COALESCE(NEW.enrichment_data->'vehicle_classification'->>'model', '') || ' ' ||
                        COALESCE(NEW.enrichment_data->'vehicle_classification'->>'color', '');
                    IF NEW.enrichment_data->'vehicle_classification'->>'make' IS NOT NULL THEN
                        labels_array := labels_array || to_jsonb(NEW.enrichment_data->'vehicle_classification'->>'make');
                    END IF;
                    IF NEW.enrichment_data->'vehicle_classification'->>'model' IS NOT NULL THEN
                        labels_array := labels_array || to_jsonb(NEW.enrichment_data->'vehicle_classification'->>'model');
                    END IF;
                END IF;
                IF NEW.enrichment_data ? 'pet_classification' THEN
                    enrichment_text := enrichment_text || ' ' ||
                        COALESCE(NEW.enrichment_data->'pet_classification'->>'breed', '') || ' ' ||
                        COALESCE(NEW.enrichment_data->'pet_classification'->>'species', '');
                    IF NEW.enrichment_data->'pet_classification'->>'breed' IS NOT NULL THEN
                        labels_array := labels_array || to_jsonb(NEW.enrichment_data->'pet_classification'->>'breed');
                    END IF;
                END IF;
            END IF;

            IF NEW.object_type IS NOT NULL THEN
                labels_array := labels_array || to_jsonb(NEW.object_type);
            END IF;

            NEW.labels := (SELECT jsonb_agg(DISTINCT value) FROM jsonb_array_elements_text(labels_array) AS value);
            NEW.search_vector := to_tsvector('english',
                COALESCE(NEW.object_type, '') || ' ' ||
                COALESCE(camera_name_text, '') || ' ' ||
                enrichment_text
            );
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE TRIGGER detections_search_vector_trigger
        BEFORE INSERT OR UPDATE ON detections
        FOR EACH ROW EXECUTE FUNCTION detections_search_vector_update();
        """
    )

    op.execute(
        """
        UPDATE detections d SET
            labels = (
                SELECT jsonb_agg(DISTINCT value) FILTER (WHERE value IS NOT NULL)
                FROM (
                    SELECT d.object_type AS value
                    UNION ALL
                    SELECT d.enrichment_data->'vehicle_classification'->>'make'
                    WHERE d.enrichment_data ? 'vehicle_classification'
                    UNION ALL
                    SELECT d.enrichment_data->'pet_classification'->>'breed'
                    WHERE d.enrichment_data ? 'pet_classification'
                ) AS labels
            );
        """
    )

    op.execute(
        """
        UPDATE detections d SET
            search_vector = to_tsvector('english',
                COALESCE(d.object_type, '') || ' ' ||
                COALESCE(c.name, '') || ' ' ||
                COALESCE(d.enrichment_data->'vehicle_classification'->>'make', '') || ' ' ||
                COALESCE(d.enrichment_data->'pet_classification'->>'breed', '')
            )
        FROM cameras c
        WHERE d.camera_id = c.id;
        """
    )

    op.create_index(
        "idx_detections_search_vector",
        "detections",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )

    op.create_index(
        "idx_detections_labels_gin",
        "detections",
        ["labels"],
        unique=False,
        postgresql_using="gin",
    )


def downgrade() -> None:
    """Remove full-text search vector column and trigger from detections table."""
    op.execute("DROP TRIGGER IF EXISTS detections_search_vector_trigger ON detections;")
    op.execute("DROP FUNCTION IF EXISTS detections_search_vector_update();")
    op.drop_index("idx_detections_search_vector", table_name="detections")
    op.drop_index("idx_detections_labels_gin", table_name="detections")
    op.drop_column("detections", "search_vector")
    op.drop_column("detections", "labels")
