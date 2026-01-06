"""merge database optimization heads

Revision ID: 00c8a000b44f
Revises: add_gin_brin_specialized_indexes, add_time_series_partitioning
Create Date: 2026-01-06 11:40:41.274364

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "00c8a000b44f"
down_revision: str | Sequence[str] | None = (
    "add_gin_brin_specialized_indexes",
    "add_time_series_partitioning",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
