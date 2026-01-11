"""Add indexes on alerts table for deduplication performance

Revision ID: add_alerts_dedup_indexes
Revises: add_prompt_configs
Create Date: 2026-01-05 12:00:00.000000

This migration adds additional indexes to the alerts table to improve
deduplication query performance:

1. idx_alerts_delivered_at: Index on delivered_at column for queries that
   filter or sort by delivery timestamp (e.g., finding recently delivered
   alerts, checking delivery status).

2. idx_alerts_event_rule_delivered: Composite index on (event_id, rule_id,
   delivered_at) for deduplication queries that need to check if an alert
   was already delivered for a specific event/rule combination within a
   time window.

These indexes complement the existing dedup_key-based indexes by providing
additional query paths for deduplication logic that considers delivery
timestamps.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_alerts_dedup_indexes"
down_revision: str | Sequence[str] | None = "add_prompt_configs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add indexes for alert deduplication performance."""
    # Index on delivered_at for filtering/sorting by delivery timestamp
    op.create_index(
        "idx_alerts_delivered_at",
        "alerts",
        ["delivered_at"],
        unique=False,
    )

    # Composite index for deduplication queries that check event/rule/delivery
    op.create_index(
        "idx_alerts_event_rule_delivered",
        "alerts",
        ["event_id", "rule_id", "delivered_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove deduplication indexes."""
    op.drop_index("idx_alerts_event_rule_delivered", table_name="alerts", if_exists=True)
    op.drop_index("idx_alerts_delivered_at", table_name="alerts", if_exists=True)
