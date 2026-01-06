"""merge heads

Revision ID: d4cdaa821492
Revises: add_object_types_gin_trgm, add_prompt_versions
Create Date: 2026-01-04 07:27:29.290381

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "d4cdaa821492"
down_revision: str | Sequence[str] | None = ("add_object_types_gin_trgm", "add_prompt_versions")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
