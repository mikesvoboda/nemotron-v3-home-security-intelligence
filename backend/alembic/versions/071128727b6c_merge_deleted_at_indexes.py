"""merge_deleted_at_indexes

Revision ID: 071128727b6c
Revises: add_deleted_at_indexes, b80664ed1373
Create Date: 2026-01-14 00:06:58.073219

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "071128727b6c"
down_revision: str | Sequence[str] | None = (
    "add_deleted_at_indexes",
    "b80664ed1373",  # pragma: allowlist secret
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
