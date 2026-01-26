"""Add action_events table for X-CLIP action recognition results.

Revision ID: 0012
Revises: 0011
Create Date: 2026-01-26

This migration creates the action_events table for storing X-CLIP
action recognition results. The table stores detected actions from
video frame sequences, including confidence scores and security flags.

Linear issue: NEM-3714
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create action_events table with indexes and constraints."""
    op.create_table(
        "action_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "camera_id",
            sa.String(),
            nullable=False,
            comment="Camera where action was detected",
        ),
        sa.Column(
            "track_id",
            sa.Integer(),
            nullable=True,
            comment="Optional reference to tracked object",
        ),
        sa.Column(
            "action",
            sa.String(100),
            nullable=False,
            comment="Detected action: walking normally, climbing, etc.",
        ),
        sa.Column(
            "confidence",
            sa.Float(),
            nullable=False,
            comment="Action classification confidence (0.0 to 1.0)",
        ),
        sa.Column(
            "is_suspicious",
            sa.Boolean(),
            nullable=False,
            default=False,
            comment="Whether the action is flagged as security-relevant",
        ),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="When the action was detected",
        ),
        sa.Column(
            "frame_count",
            sa.Integer(),
            nullable=False,
            server_default="8",
            comment="Number of frames analyzed for this action",
        ),
        sa.Column(
            "all_scores",
            JSONB(),
            nullable=True,
            comment="Dict of action -> score for all candidates",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # Primary key constraint
        sa.PrimaryKeyConstraint("id"),
        # Foreign key constraints
        sa.ForeignKeyConstraint(
            ["camera_id"],
            ["cameras.id"],
            name="fk_action_events_camera_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["track_id"],
            ["tracks.id"],
            name="fk_action_events_track_id",
            ondelete="SET NULL",
        ),
        # Check constraints for valid values
        sa.CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_action_events_confidence_range",
        ),
        sa.CheckConstraint(
            "frame_count > 0",
            name="ck_action_events_frame_count_positive",
        ),
    )

    # Create indexes for efficient querying
    op.create_index("idx_action_events_camera_id", "action_events", ["camera_id"])
    op.create_index("idx_action_events_track_id", "action_events", ["track_id"])
    op.create_index("idx_action_events_timestamp", "action_events", ["timestamp"])
    op.create_index("idx_action_events_action", "action_events", ["action"])
    op.create_index("idx_action_events_is_suspicious", "action_events", ["is_suspicious"])

    # Composite indexes for common query patterns
    op.create_index(
        "idx_action_events_camera_suspicious",
        "action_events",
        ["camera_id", "is_suspicious"],
    )
    op.create_index(
        "idx_action_events_camera_time",
        "action_events",
        ["camera_id", "timestamp"],
    )

    # BRIN index for time-series queries (efficient for chronological data)
    op.create_index(
        "ix_action_events_timestamp_brin",
        "action_events",
        ["timestamp"],
        postgresql_using="brin",
    )


def downgrade() -> None:
    """Drop action_events table and its indexes."""
    # Drop indexes first
    op.drop_index("ix_action_events_timestamp_brin", table_name="action_events")
    op.drop_index("idx_action_events_camera_time", table_name="action_events")
    op.drop_index("idx_action_events_camera_suspicious", table_name="action_events")
    op.drop_index("idx_action_events_is_suspicious", table_name="action_events")
    op.drop_index("idx_action_events_action", table_name="action_events")
    op.drop_index("idx_action_events_timestamp", table_name="action_events")
    op.drop_index("idx_action_events_track_id", table_name="action_events")
    op.drop_index("idx_action_events_camera_id", table_name="action_events")

    # Drop table
    op.drop_table("action_events")
