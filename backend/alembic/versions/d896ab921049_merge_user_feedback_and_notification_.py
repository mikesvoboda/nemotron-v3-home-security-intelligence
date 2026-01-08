"""merge user feedback and notification preferences heads

Revision ID: d896ab921049
Revises: add_user_feedback_calibration, eb2e0919ec02
Create Date: 2026-01-08 10:59:14.919181

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "d896ab921049"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("add_user_feedback_calibration", "eb2e0919ec02")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
