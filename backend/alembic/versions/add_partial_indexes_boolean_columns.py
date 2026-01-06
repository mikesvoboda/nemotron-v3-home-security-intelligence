"""Add partial indexes for boolean filter columns

Revision ID: add_partial_indexes_boolean
Revises: add_alerts_dedup_indexes
Create Date: 2026-01-06 12:00:00.000000

This migration adds partial indexes for boolean columns that are commonly
filtered in queries. Partial indexes are more efficient than full indexes
for boolean columns because:

1. They only index rows matching the WHERE clause (typically 10-20% of data)
2. They use less disk space
3. They're faster to maintain on INSERT/UPDATE
4. They provide better query performance for the common query pattern

Partial indexes created:

1. idx_events_reviewed_false: Index on events WHERE reviewed = false
   - Use case: Dashboard shows unreviewed events, this is the common query pattern

2. idx_events_is_fast_path_true: Index on events WHERE is_fast_path = true
   - Use case: Query fast-path analyzed events for debugging/monitoring

3. idx_zones_enabled_true: Index on zones WHERE enabled = true
   - Use case: Detection pipeline only processes enabled zones

4. idx_alert_rules_enabled_true: Index on alert_rules WHERE enabled = true
   - Use case: Alert system only evaluates enabled rules

5. idx_api_keys_is_active_true: Index on api_keys WHERE is_active = true
   - Use case: Authentication middleware only checks active keys

6. idx_prompt_versions_is_active_true: Index on prompt_versions WHERE is_active = true
   - Use case: AI services only load active prompt versions

7. idx_scene_changes_acknowledged_false: Index on scene_changes WHERE acknowledged = false
   - Use case: Dashboard shows unacknowledged scene changes for review
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_partial_indexes_boolean"
down_revision: str | Sequence[str] | None = "add_alerts_dedup_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add partial indexes for commonly filtered boolean columns."""

    # Events: Index unreviewed events (common dashboard query)
    op.create_index(
        "idx_events_reviewed_false",
        "events",
        ["reviewed"],
        unique=False,
        postgresql_where=sa.text("reviewed = false"),
    )

    # Events: Index fast-path events (monitoring/debugging queries)
    op.create_index(
        "idx_events_is_fast_path_true",
        "events",
        ["is_fast_path"],
        unique=False,
        postgresql_where=sa.text("is_fast_path = true"),
    )

    # Zones: Index enabled zones (detection pipeline queries)
    op.create_index(
        "idx_zones_enabled_true",
        "zones",
        ["enabled"],
        unique=False,
        postgresql_where=sa.text("enabled = true"),
    )

    # Alert Rules: Index enabled rules (alert evaluation queries)
    op.create_index(
        "idx_alert_rules_enabled_true",
        "alert_rules",
        ["enabled"],
        unique=False,
        postgresql_where=sa.text("enabled = true"),
    )

    # API Keys: Index active keys (authentication queries)
    op.create_index(
        "idx_api_keys_is_active_true",
        "api_keys",
        ["is_active"],
        unique=False,
        postgresql_where=sa.text("is_active = true"),
    )

    # Prompt Versions: Index active versions (AI service queries)
    op.create_index(
        "idx_prompt_versions_is_active_true",
        "prompt_versions",
        ["is_active"],
        unique=False,
        postgresql_where=sa.text("is_active = true"),
    )

    # Scene Changes: Index unacknowledged changes (dashboard queries)
    op.create_index(
        "idx_scene_changes_acknowledged_false",
        "scene_changes",
        ["acknowledged"],
        unique=False,
        postgresql_where=sa.text("acknowledged = false"),
    )


def downgrade() -> None:
    """Remove partial indexes for boolean columns."""
    op.drop_index("idx_scene_changes_acknowledged_false", table_name="scene_changes")
    op.drop_index("idx_prompt_versions_is_active_true", table_name="prompt_versions")
    op.drop_index("idx_api_keys_is_active_true", table_name="api_keys")
    op.drop_index("idx_alert_rules_enabled_true", table_name="alert_rules")
    op.drop_index("idx_zones_enabled_true", table_name="zones")
    op.drop_index("idx_events_is_fast_path_true", table_name="events")
    op.drop_index("idx_events_reviewed_false", table_name="events")
