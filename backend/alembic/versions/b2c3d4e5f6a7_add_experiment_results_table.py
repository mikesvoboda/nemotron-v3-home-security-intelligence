"""add_experiment_results_table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-01-19 18:00:00.000000

This migration adds the experiment_results table for tracking prompt A/B test
comparisons. This enables shadow mode validation and A/B testing of new prompts.

Tables created:
- experiment_results: Stores side-by-side comparison results from V1/V2 prompts

NEM-3023: Deploy prompt improvements via shadow mode and validate with A/B testing
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create experiment_results table for prompt A/B testing."""

    # =========================================================================
    # EXPERIMENT RESULTS TABLE
    # =========================================================================

    op.create_table(
        "experiment_results",
        # Primary key
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        # Experiment identification
        sa.Column("experiment_name", sa.String(100), nullable=False),
        sa.Column("experiment_version", sa.String(50), nullable=False),
        # Context
        sa.Column("camera_id", sa.String(50), nullable=False),
        sa.Column("batch_id", sa.String(100), nullable=True),
        sa.Column("event_id", sa.Integer(), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # V1 (control) results
        sa.Column("v1_risk_score", sa.Integer(), nullable=False),
        sa.Column("v1_risk_level", sa.String(20), nullable=True),
        sa.Column("v1_latency_ms", sa.Float(), nullable=False),
        # V2 (treatment) results
        sa.Column("v2_risk_score", sa.Integer(), nullable=False),
        sa.Column("v2_risk_level", sa.String(20), nullable=True),
        sa.Column("v2_latency_ms", sa.Float(), nullable=False),
        # Pre-calculated diff for query convenience
        sa.Column("score_diff", sa.Integer(), nullable=True),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="SET NULL"),
    )

    # =========================================================================
    # INDEXES
    # =========================================================================

    # Index for filtering by experiment name and time (common query pattern)
    op.create_index(
        "ix_experiment_results_experiment_created",
        "experiment_results",
        ["experiment_name", "created_at"],
    )

    # Index for filtering by camera (analysis per camera)
    op.create_index(
        "ix_experiment_results_camera_created",
        "experiment_results",
        ["camera_id", "created_at"],
    )

    # Index for time-based queries (cleanup, rolling windows)
    op.create_index(
        "ix_experiment_results_created_at",
        "experiment_results",
        ["created_at"],
    )


def downgrade() -> None:
    """Drop experiment_results table."""

    # Drop indexes first
    op.drop_index("ix_experiment_results_created_at", table_name="experiment_results")
    op.drop_index("ix_experiment_results_camera_created", table_name="experiment_results")
    op.drop_index("ix_experiment_results_experiment_created", table_name="experiment_results")

    # Drop table
    op.drop_table("experiment_results")
