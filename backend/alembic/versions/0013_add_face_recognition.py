"""Add face recognition tables.

Revision ID: 0013
Revises: 0012
Create Date: 2026-01-26

This migration creates tables for face recognition:
- known_persons: Registered persons for face recognition
- face_embeddings: ArcFace embeddings for known persons
- face_detection_events: Face detection events from cameras

Implements NEM-3716: Face detection with InsightFace
Implements NEM-3717: Face quality assessment for recognition
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create face recognition tables with indexes and constraints."""
    # Create known_persons table
    op.create_table(
        "known_persons",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "is_household_member",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for known_persons
    op.create_index(
        "idx_known_persons_name",
        "known_persons",
        ["name"],
    )
    op.create_index(
        "idx_known_persons_household",
        "known_persons",
        ["is_household_member"],
    )

    # Create face_embeddings table
    op.create_table(
        "face_embeddings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column(
            "embedding",
            sa.LargeBinary(),
            nullable=False,
            comment="Serialized 512-dim float32 ArcFace embedding",
        ),
        sa.Column(
            "quality_score",
            sa.Float(),
            nullable=False,
            server_default="1.0",
            comment="Face quality score when embedding was captured (0-1)",
        ),
        sa.Column(
            "source_image_path",
            sa.String(500),
            nullable=True,
            comment="Path to the source image",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["known_persons.id"],
            name="fk_face_embeddings_person_id",
            ondelete="CASCADE",
        ),
    )

    # Create indexes for face_embeddings
    op.create_index(
        "idx_face_embeddings_person_id",
        "face_embeddings",
        ["person_id"],
    )
    op.create_index(
        "idx_face_embeddings_quality",
        "face_embeddings",
        ["quality_score"],
    )

    # Create face_detection_events table
    op.create_table(
        "face_detection_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("camera_id", sa.String(), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When the face was detected",
        ),
        sa.Column(
            "bbox",
            JSONB(),
            nullable=False,
            comment="Bounding box coordinates [x1, y1, x2, y2]",
        ),
        sa.Column(
            "embedding",
            sa.LargeBinary(),
            nullable=False,
            comment="Serialized 512-dim float32 ArcFace embedding",
        ),
        sa.Column(
            "matched_person_id",
            sa.Integer(),
            nullable=True,
            comment="FK to matched known person (NULL if unknown)",
        ),
        sa.Column(
            "match_confidence",
            sa.Float(),
            nullable=True,
            comment="Cosine similarity with matched person",
        ),
        sa.Column(
            "is_unknown",
            sa.Boolean(),
            nullable=False,
            server_default="true",
            comment="True if face is unknown (no match found)",
        ),
        sa.Column(
            "quality_score",
            sa.Float(),
            nullable=False,
            server_default="0.0",
            comment="Face quality score (0-1)",
        ),
        sa.Column(
            "age_estimate",
            sa.Integer(),
            nullable=True,
            comment="Estimated age",
        ),
        sa.Column(
            "gender_estimate",
            sa.String(1),
            nullable=True,
            comment="Estimated gender (M/F)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["camera_id"],
            ["cameras.id"],
            name="fk_face_events_camera_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["matched_person_id"],
            ["known_persons.id"],
            name="fk_face_events_matched_person_id",
            ondelete="SET NULL",
        ),
        # Check constraint for gender values
        sa.CheckConstraint(
            "gender_estimate IS NULL OR gender_estimate IN ('M', 'F')",
            name="ck_face_events_gender_valid",
        ),
        # Check constraint for quality score range
        sa.CheckConstraint(
            "quality_score >= 0 AND quality_score <= 1",
            name="ck_face_events_quality_range",
        ),
        # Check constraint for match confidence range
        sa.CheckConstraint(
            "match_confidence IS NULL OR (match_confidence >= -1 AND match_confidence <= 1)",
            name="ck_face_events_confidence_range",
        ),
    )

    # Create indexes for face_detection_events
    op.create_index(
        "idx_face_events_camera_id",
        "face_detection_events",
        ["camera_id"],
    )
    op.create_index(
        "idx_face_events_timestamp",
        "face_detection_events",
        ["timestamp"],
    )
    op.create_index(
        "idx_face_events_is_unknown",
        "face_detection_events",
        ["is_unknown"],
    )
    op.create_index(
        "idx_face_events_matched_person_id",
        "face_detection_events",
        ["matched_person_id"],
    )
    op.create_index(
        "idx_face_events_camera_timestamp",
        "face_detection_events",
        ["camera_id", "timestamp"],
    )
    # BRIN index for time-series queries
    op.create_index(
        "idx_face_events_timestamp_brin",
        "face_detection_events",
        ["timestamp"],
        postgresql_using="brin",
    )


def downgrade() -> None:
    """Drop face recognition tables and indexes."""
    # Drop face_detection_events indexes first
    op.drop_index("idx_face_events_timestamp_brin", table_name="face_detection_events")
    op.drop_index("idx_face_events_camera_timestamp", table_name="face_detection_events")
    op.drop_index("idx_face_events_matched_person_id", table_name="face_detection_events")
    op.drop_index("idx_face_events_is_unknown", table_name="face_detection_events")
    op.drop_index("idx_face_events_timestamp", table_name="face_detection_events")
    op.drop_index("idx_face_events_camera_id", table_name="face_detection_events")

    # Drop face_embeddings indexes
    op.drop_index("idx_face_embeddings_quality", table_name="face_embeddings")
    op.drop_index("idx_face_embeddings_person_id", table_name="face_embeddings")

    # Drop known_persons indexes
    op.drop_index("idx_known_persons_household", table_name="known_persons")
    op.drop_index("idx_known_persons_name", table_name="known_persons")

    # Drop tables in reverse order (respect foreign keys)
    op.drop_table("face_detection_events")
    op.drop_table("face_embeddings")
    op.drop_table("known_persons")
