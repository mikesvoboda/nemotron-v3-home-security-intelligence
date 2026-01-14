"""merge migration branches

Revision ID: b80664ed1373
Revises: add_alert_version_id_column, add_row_version_pv
Create Date: 2026-01-13 21:24:06.535142

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "b80664ed1373"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("add_alert_version_id_column", "add_row_version_pv")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
