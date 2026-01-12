"""merge_add_4_feedback_types_and_job_transitions

Revision ID: 6b206d6591cb
Revises: add_4_feedback_types, add_job_transitions
Create Date: 2026-01-12 13:36:23.676255

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "6b206d6591cb"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("add_4_feedback_types", "add_job_transitions")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
