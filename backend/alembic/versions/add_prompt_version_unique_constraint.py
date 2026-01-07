"""Add unique constraint to prompt_versions table

Revision ID: add_prompt_version_uq
Revises: add_alerts_rules
Create Date: 2026-01-07 12:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_prompt_version_uq"
down_revision: str | Sequence[str] | None = "add_alerts_rules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add unique constraint on (model, version) to prompt_versions table."""
    op.create_unique_constraint(
        "uq_prompt_version_model_version",
        "prompt_versions",
        ["model", "version"],
    )


def downgrade() -> None:
    """Drop unique constraint from prompt_versions table."""
    op.drop_constraint(
        "uq_prompt_version_model_version",
        "prompt_versions",
        type_="unique",
    )
