"""Add event_audits table for AI pipeline performance tracking

Revision ID: add_event_audits
Revises: add_llm_prompt
Create Date: 2026-01-02 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_event_audits"
down_revision: str | Sequence[str] | None = "add_llm_prompt"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create event_audits table."""
    op.create_table(
        "event_audits",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("audited_at", sa.DateTime(timezone=True), nullable=False),
        # Model contribution flags
        sa.Column("has_rtdetr", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("has_florence", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("has_clip", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("has_violence", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("has_clothing", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("has_vehicle", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("has_pet", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("has_weather", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("has_image_quality", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("has_zones", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("has_baseline", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("has_cross_camera", sa.Boolean(), nullable=False, server_default="false"),
        # Prompt metrics
        sa.Column("prompt_length", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prompt_token_estimate", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("enrichment_utilization", sa.Float(), nullable=False, server_default="0.0"),
        # Self-evaluation scores
        sa.Column("context_usage_score", sa.Float(), nullable=True),
        sa.Column("reasoning_coherence_score", sa.Float(), nullable=True),
        sa.Column("risk_justification_score", sa.Float(), nullable=True),
        sa.Column("consistency_score", sa.Float(), nullable=True),
        sa.Column("overall_quality_score", sa.Float(), nullable=True),
        # Consistency check
        sa.Column("consistency_risk_score", sa.Integer(), nullable=True),
        sa.Column("consistency_diff", sa.Integer(), nullable=True),
        # Self-evaluation text
        sa.Column("self_eval_critique", sa.Text(), nullable=True),
        sa.Column("self_eval_prompt", sa.Text(), nullable=True),
        sa.Column("self_eval_response", sa.Text(), nullable=True),
        # Prompt improvements (JSON as text)
        sa.Column("missing_context", sa.Text(), nullable=True),
        sa.Column("confusing_sections", sa.Text(), nullable=True),
        sa.Column("unused_data", sa.Text(), nullable=True),
        sa.Column("format_suggestions", sa.Text(), nullable=True),
        sa.Column("model_gaps", sa.Text(), nullable=True),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("event_id"),
    )

    # Create indexes
    op.create_index("idx_event_audits_event_id", "event_audits", ["event_id"])
    op.create_index("idx_event_audits_audited_at", "event_audits", ["audited_at"])
    op.create_index("idx_event_audits_overall_score", "event_audits", ["overall_quality_score"])


def downgrade() -> None:
    """Drop event_audits table."""
    op.drop_index("idx_event_audits_overall_score", "event_audits")
    op.drop_index("idx_event_audits_audited_at", "event_audits")
    op.drop_index("idx_event_audits_event_id", "event_audits")
    op.drop_table("event_audits")
