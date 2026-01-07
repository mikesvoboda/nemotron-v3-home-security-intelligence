"""merge heads add_notification_preferences and add_prompt_version_uq

Revision ID: eb2e0919ec02
Revises: add_notification_preferences, add_prompt_version_uq
Create Date: 2026-01-07 17:20:28.101019

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "eb2e0919ec02"
down_revision: str | Sequence[str] | None = (
    "add_notification_preferences",
    "add_prompt_version_uq",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
