"""Add prompt_versions table for AI prompt configuration tracking

Revision ID: add_prompt_versions
Revises: add_event_audits
Create Date: 2026-01-04 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_prompt_versions"
down_revision: str | Sequence[str] | None = "add_event_audits"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create prompt_versions table."""
    op.create_table(
        "prompt_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "model",
            sa.Enum(
                "nemotron",
                "florence2",
                "yolo_world",
                "xclip",
                "fashion_clip",
                name="aimodel",
            ),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("config_json", sa.Text(), nullable=False),
        sa.Column("change_description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes
    op.create_index("idx_prompt_versions_model", "prompt_versions", ["model"])
    op.create_index("idx_prompt_versions_model_version", "prompt_versions", ["model", "version"])
    op.create_index("idx_prompt_versions_model_active", "prompt_versions", ["model", "is_active"])
    op.create_index("idx_prompt_versions_created_at", "prompt_versions", ["created_at"])


def downgrade() -> None:
    """Drop prompt_versions table."""
    op.drop_index("idx_prompt_versions_created_at", "prompt_versions")
    op.drop_index("idx_prompt_versions_model_active", "prompt_versions")
    op.drop_index("idx_prompt_versions_model_version", "prompt_versions")
    op.drop_index("idx_prompt_versions_model", "prompt_versions")
    op.drop_table("prompt_versions")
    # Drop the enum type
    op.execute("DROP TYPE IF EXISTS aimodel")
