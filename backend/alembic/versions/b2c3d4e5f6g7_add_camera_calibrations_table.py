"""add_camera_calibrations_table

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-01-19 13:00:00.000000

This migration adds the camera_calibrations table for per-camera risk calibration
learned from user feedback. The calibration system adjusts risk scores based on
false positive rates to reduce over-alerting from specific cameras.

Tables created:
- camera_calibrations: Per-camera risk calibration learned from feedback

NEM-3022: Implement camera calibration model and feedback-driven risk adjustment
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6g7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create camera_calibrations table."""

    # =========================================================================
    # CAMERA CALIBRATIONS TABLE
    # =========================================================================

    op.create_table(
        "camera_calibrations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("camera_id", sa.String(), nullable=False),
        # Aggregate metrics
        sa.Column("total_feedback_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("false_positive_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("false_positive_rate", sa.Float(), nullable=False, server_default="0.0"),
        # Score adjustment (-30 to +30)
        sa.Column("risk_offset", sa.Integer(), nullable=False, server_default="0"),
        # Model-specific adjustments (JSONB)
        sa.Column(
            "model_weights",
            JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        # Pattern-specific suppression (JSONB array)
        sa.Column(
            "suppress_patterns",
            JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        # Computed stats
        sa.Column("avg_model_score", sa.Float(), nullable=True),
        sa.Column("avg_user_suggested_score", sa.Float(), nullable=True),
        # Timestamp
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["camera_id"],
            ["cameras.id"],
            ondelete="CASCADE",
        ),
        # Unique constraint on camera_id
        sa.UniqueConstraint("camera_id", name="uq_camera_calibrations_camera_id"),
    )

    # Create index for camera_id lookup
    op.create_index("idx_camera_calibrations_camera_id", "camera_calibrations", ["camera_id"])

    # =========================================================================
    # CHECK CONSTRAINTS
    # =========================================================================

    # Risk offset range constraint (-30 to +30)
    op.create_check_constraint(
        "ck_camera_calibrations_risk_offset_range",
        "camera_calibrations",
        "risk_offset >= -30 AND risk_offset <= 30",
    )

    # False positive rate range constraint (0.0 to 1.0)
    op.create_check_constraint(
        "ck_camera_calibrations_fp_rate_range",
        "camera_calibrations",
        "false_positive_rate >= 0.0 AND false_positive_rate <= 1.0",
    )

    # Feedback counts non-negative constraint
    op.create_check_constraint(
        "ck_camera_calibrations_feedback_count",
        "camera_calibrations",
        "total_feedback_count >= 0 AND false_positive_count >= 0",
    )


def downgrade() -> None:
    """Drop camera_calibrations table."""

    # Drop check constraints first
    op.drop_constraint(
        "ck_camera_calibrations_feedback_count",
        "camera_calibrations",
        type_="check",
    )
    op.drop_constraint(
        "ck_camera_calibrations_fp_rate_range",
        "camera_calibrations",
        type_="check",
    )
    op.drop_constraint(
        "ck_camera_calibrations_risk_offset_range",
        "camera_calibrations",
        type_="check",
    )

    # Drop index
    op.drop_index("idx_camera_calibrations_camera_id", table_name="camera_calibrations")

    # Drop table
    op.drop_table("camera_calibrations")
