"""Add prompt_configs table for database-backed prompt configuration storage

Revision ID: add_prompt_configs
Revises: d4cdaa821492
Create Date: 2026-01-05 12:00:00.000000

This migration creates the prompt_configs table for storing AI model prompt
configurations. This supports the Prompt Playground "Save" functionality,
allowing users to persist custom prompts, temperature, and token settings.

The table uses a unique constraint on the model column to ensure only one
active configuration per model. Version numbers are incremented on each update
to track configuration history.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_prompt_configs"
down_revision: str | Sequence[str] | None = "d4cdaa821492"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create prompt_configs table."""
    op.create_table(
        "prompt_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("model", sa.String(50), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("max_tokens", sa.Integer(), nullable=False, server_default="2048"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
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
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create unique index on model column
    op.create_index(
        "idx_prompt_configs_model",
        "prompt_configs",
        ["model"],
        unique=True,
    )

    # Create index on updated_at for sorting
    op.create_index(
        "idx_prompt_configs_updated_at",
        "prompt_configs",
        ["updated_at"],
    )


def downgrade() -> None:
    """Drop prompt_configs table."""
    op.drop_index("idx_prompt_configs_updated_at", "prompt_configs")
    op.drop_index("idx_prompt_configs_model", "prompt_configs")
    op.drop_table("prompt_configs")
