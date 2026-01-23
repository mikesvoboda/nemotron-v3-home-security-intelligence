"""enhance event feedback model

Revision ID: f6g7h8i9j0k1
Revises: e5f6g7h8i9j0
Create Date: 2026-01-23 10:00:00.000000

This migration enhances the EventFeedback model with additional fields for
Nemotron prompt improvement calibration. These fields enable a feedback loop
where user corrections can improve future AI analysis.

New fields:
- actual_threat_level: User's assessment ("no_threat", "minor_concern", "genuine_threat")
- suggested_score: What user thinks score should have been (0-100)
- actual_identity: Identity correction for household member learning
- what_was_wrong: Detailed explanation of AI failure
- model_failures: JSONB list of specific AI models that failed

Changes:
- Adds 5 new columns to event_feedback table
- Adds CHECK constraints for valid values
- Adds index for actual_threat_level for calibration queries

Implements NEM-3330: Enhance EventFeedback model.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6g7h8i9j0k1"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = "e5f6g7h8i9j0"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add enhanced feedback fields to event_feedback table."""

    # =========================================================================
    # ADD NEW COLUMNS
    # =========================================================================

    # actual_threat_level: User's assessment of true threat level
    op.add_column(
        "event_feedback",
        sa.Column("actual_threat_level", sa.String(20), nullable=True),
    )

    # suggested_score: What user thinks score should have been (0-100)
    op.add_column(
        "event_feedback",
        sa.Column("suggested_score", sa.Integer(), nullable=True),
    )

    # actual_identity: Identity correction for household member learning
    op.add_column(
        "event_feedback",
        sa.Column("actual_identity", sa.String(100), nullable=True),
    )

    # what_was_wrong: Detailed explanation of AI failure
    op.add_column(
        "event_feedback",
        sa.Column("what_was_wrong", sa.Text(), nullable=True),
    )

    # model_failures: JSONB list of specific AI models that failed
    op.add_column(
        "event_feedback",
        sa.Column(
            "model_failures",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )

    # =========================================================================
    # ADD CHECK CONSTRAINTS
    # =========================================================================

    # CHECK constraint for actual_threat_level values
    op.create_check_constraint(
        "ck_event_feedback_actual_threat_level",
        "event_feedback",
        "actual_threat_level IS NULL OR actual_threat_level IN ('no_threat', 'minor_concern', 'genuine_threat')",
    )

    # CHECK constraint for suggested_score range (0-100)
    op.create_check_constraint(
        "ck_event_feedback_suggested_score",
        "event_feedback",
        "suggested_score IS NULL OR (suggested_score >= 0 AND suggested_score <= 100)",
    )

    # =========================================================================
    # ADD INDEXES
    # =========================================================================

    # Index for filtering by actual_threat_level (calibration queries)
    op.create_index(
        "idx_event_feedback_actual_threat_level",
        "event_feedback",
        ["actual_threat_level"],
    )


def downgrade() -> None:
    """Remove enhanced feedback fields from event_feedback table."""

    # =========================================================================
    # DROP INDEXES
    # =========================================================================
    op.drop_index(
        "idx_event_feedback_actual_threat_level",
        table_name="event_feedback",
    )

    # =========================================================================
    # DROP CHECK CONSTRAINTS
    # =========================================================================
    op.drop_constraint(
        "ck_event_feedback_suggested_score",
        "event_feedback",
        type_="check",
    )
    op.drop_constraint(
        "ck_event_feedback_actual_threat_level",
        "event_feedback",
        type_="check",
    )

    # =========================================================================
    # DROP COLUMNS
    # =========================================================================
    op.drop_column("event_feedback", "model_failures")
    op.drop_column("event_feedback", "what_was_wrong")
    op.drop_column("event_feedback", "actual_identity")
    op.drop_column("event_feedback", "suggested_score")
    op.drop_column("event_feedback", "actual_threat_level")
