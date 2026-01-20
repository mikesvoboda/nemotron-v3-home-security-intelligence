"""Add enrichment result tables

Revision ID: a7b8c9d10e11
Revises: e36700c35af6
Create Date: 2026-01-19 10:00:00.000000

This migration adds tables for storing on-demand AI model enrichment results:
- pose_results: YOLOv8n-pose body posture detection
- threat_detections: Threat-Detection-YOLOv8n weapon detection
- demographics_results: Age-Gender prediction
- reid_embeddings: OSNet person re-identification embeddings
- action_results: X-CLIP action recognition

See: docs/plans/2026-01-19-model-zoo-prompt-improvements-design.md Section 6
Related Linear issue: NEM-3042
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7b8c9d10e11"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = "e36700c35af6"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create enrichment result tables for on-demand AI models."""

    # =========================================================================
    # pose_results - YOLOv8n-pose body posture detection
    # =========================================================================
    op.create_table(
        "pose_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("detection_id", sa.Integer(), nullable=False),
        sa.Column(
            "keypoints",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="17 COCO keypoints as [[x, y, conf], ...]",
        ),
        sa.Column(
            "pose_class",
            sa.String(50),
            nullable=True,
            comment="Classified pose: standing, crouching, etc.",
        ),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("is_suspicious", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["detection_id"],
            ["detections.id"],
            name="fk_pose_results_detection_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("detection_id", name="uq_pose_results_detection_id"),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)",
            name="ck_pose_results_confidence_range",
        ),
        sa.CheckConstraint(
            "pose_class IS NULL OR pose_class IN ('standing', 'crouching', 'bending_over', "
            "'arms_raised', 'sitting', 'lying_down', 'unknown')",
            name="ck_pose_results_pose_class",
        ),
    )
    op.create_index("idx_pose_results_detection_id", "pose_results", ["detection_id"])
    op.create_index("idx_pose_results_created_at", "pose_results", ["created_at"])
    op.create_index("idx_pose_results_is_suspicious", "pose_results", ["is_suspicious"])

    # =========================================================================
    # threat_detections - Threat-Detection-YOLOv8n weapon detection
    # =========================================================================
    op.create_table(
        "threat_detections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("detection_id", sa.Integer(), nullable=False),
        sa.Column(
            "threat_type",
            sa.String(50),
            nullable=False,
            comment="Type of threat: gun, knife, etc.",
        ),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column(
            "severity",
            sa.String(20),
            nullable=False,
            comment="Severity: critical, high, medium",
        ),
        sa.Column(
            "bbox",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Bounding box as [x1, y1, x2, y2]",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["detection_id"],
            ["detections.id"],
            name="fk_threat_detections_detection_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_threat_detections_confidence_range",
        ),
        sa.CheckConstraint(
            "severity IN ('critical', 'high', 'medium', 'low')",
            name="ck_threat_detections_severity",
        ),
        sa.CheckConstraint(
            "threat_type IN ('gun', 'knife', 'grenade', 'explosive', 'weapon', 'other')",
            name="ck_threat_detections_threat_type",
        ),
    )
    op.create_index("idx_threat_detections_detection_id", "threat_detections", ["detection_id"])
    op.create_index("idx_threat_detections_created_at", "threat_detections", ["created_at"])
    op.create_index("idx_threat_detections_threat_type", "threat_detections", ["threat_type"])
    op.create_index("idx_threat_detections_severity", "threat_detections", ["severity"])
    op.create_index(
        "idx_threat_detections_type_severity",
        "threat_detections",
        ["threat_type", "severity"],
    )

    # =========================================================================
    # demographics_results - Age-Gender prediction
    # =========================================================================
    op.create_table(
        "demographics_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("detection_id", sa.Integer(), nullable=False),
        sa.Column(
            "age_range",
            sa.String(20),
            nullable=True,
            comment="Age range: 0-10, 11-20, etc.",
        ),
        sa.Column("age_confidence", sa.Float(), nullable=True),
        sa.Column(
            "gender",
            sa.String(20),
            nullable=True,
            comment="Gender: male, female, unknown",
        ),
        sa.Column("gender_confidence", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["detection_id"],
            ["detections.id"],
            name="fk_demographics_results_detection_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("detection_id", name="uq_demographics_results_detection_id"),
        sa.CheckConstraint(
            "age_confidence IS NULL OR (age_confidence >= 0.0 AND age_confidence <= 1.0)",
            name="ck_demographics_results_age_confidence_range",
        ),
        sa.CheckConstraint(
            "gender_confidence IS NULL OR (gender_confidence >= 0.0 AND gender_confidence <= 1.0)",
            name="ck_demographics_results_gender_confidence_range",
        ),
        sa.CheckConstraint(
            "gender IS NULL OR gender IN ('male', 'female', 'unknown')",
            name="ck_demographics_results_gender",
        ),
        sa.CheckConstraint(
            "age_range IS NULL OR age_range IN ('0-10', '11-20', '21-30', '31-40', '41-50', "
            "'51-60', '61-70', '71-80', '81+', 'unknown')",
            name="ck_demographics_results_age_range",
        ),
    )
    op.create_index(
        "idx_demographics_results_detection_id", "demographics_results", ["detection_id"]
    )
    op.create_index("idx_demographics_results_created_at", "demographics_results", ["created_at"])

    # =========================================================================
    # reid_embeddings - OSNet person re-identification embeddings
    # =========================================================================
    op.create_table(
        "reid_embeddings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("detection_id", sa.Integer(), nullable=False),
        sa.Column(
            "embedding",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="512-dim feature vector as JSON array",
        ),
        sa.Column(
            "embedding_hash",
            sa.String(64),
            nullable=True,
            comment="SHA256 hash for quick lookup",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["detection_id"],
            ["detections.id"],
            name="fk_reid_embeddings_detection_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("detection_id", name="uq_reid_embeddings_detection_id"),
    )
    op.create_index("idx_reid_embeddings_detection_id", "reid_embeddings", ["detection_id"])
    op.create_index("idx_reid_embeddings_created_at", "reid_embeddings", ["created_at"])
    op.create_index("idx_reid_embeddings_embedding_hash", "reid_embeddings", ["embedding_hash"])

    # =========================================================================
    # action_results - X-CLIP action recognition
    # =========================================================================
    op.create_table(
        "action_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("detection_id", sa.Integer(), nullable=False),
        sa.Column(
            "action",
            sa.String(100),
            nullable=True,
            comment="Recognized action: walking, running, etc.",
        ),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("is_suspicious", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "all_scores",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Dict of action -> score for all candidates",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["detection_id"],
            ["detections.id"],
            name="fk_action_results_detection_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("detection_id", name="uq_action_results_detection_id"),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)",
            name="ck_action_results_confidence_range",
        ),
    )
    op.create_index("idx_action_results_detection_id", "action_results", ["detection_id"])
    op.create_index("idx_action_results_created_at", "action_results", ["created_at"])
    op.create_index("idx_action_results_action", "action_results", ["action"])
    op.create_index("idx_action_results_is_suspicious", "action_results", ["is_suspicious"])


def downgrade() -> None:
    """Drop enrichment result tables."""
    # Drop tables in reverse dependency order
    op.drop_table("action_results")
    op.drop_table("reid_embeddings")
    op.drop_table("demographics_results")
    op.drop_table("threat_detections")
    op.drop_table("pose_results")
