"""Fix DateTime columns to use timezone=True

Revision ID: fix_datetime_tz
Revises: add_clip_path
Create Date: 2025-12-31 12:30:00.000000

This migration fixes DateTime columns that were created without timezone awareness.
The models expect DateTime(timezone=True), but the initial migrations used DateTime()
without timezone, causing comparison errors between timezone-aware and naive datetimes.

This migration alters all affected columns to use TIMESTAMP WITH TIME ZONE.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fix_datetime_tz"
down_revision: str | Sequence[str] | None = "add_clip_path"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Alter DateTime columns to use timezone=True.

    PostgreSQL allows altering column types with USING to convert existing data.
    Existing naive timestamps are assumed to be in UTC.
    """
    # cameras table
    op.alter_column(
        "cameras",
        "created_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "cameras",
        "last_seen_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        postgresql_using="last_seen_at AT TIME ZONE 'UTC'",
    )

    # gpu_stats table
    op.alter_column(
        "gpu_stats",
        "recorded_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="recorded_at AT TIME ZONE 'UTC'",
    )

    # logs table
    op.alter_column(
        "logs",
        "timestamp",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="timestamp AT TIME ZONE 'UTC'",
    )

    # detections table
    op.alter_column(
        "detections",
        "detected_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="detected_at AT TIME ZONE 'UTC'",
    )

    # events table
    op.alter_column(
        "events",
        "started_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="started_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "events",
        "ended_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        postgresql_using="ended_at AT TIME ZONE 'UTC'",
    )

    # alert_rules table
    op.alter_column(
        "alert_rules",
        "created_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "alert_rules",
        "updated_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="updated_at AT TIME ZONE 'UTC'",
    )

    # alerts table
    op.alter_column(
        "alerts",
        "created_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "alerts",
        "updated_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="updated_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "alerts",
        "delivered_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        postgresql_using="delivered_at AT TIME ZONE 'UTC'",
    )

    # zones table
    op.alter_column(
        "zones",
        "created_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "zones",
        "updated_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="updated_at AT TIME ZONE 'UTC'",
    )


def downgrade() -> None:
    """Revert DateTime columns to not use timezone.

    This converts timezone-aware timestamps back to naive timestamps.
    """
    # zones table
    op.alter_column(
        "zones",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
    )
    op.alter_column(
        "zones",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
    )

    # alerts table
    op.alter_column(
        "alerts",
        "delivered_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=True,
    )
    op.alter_column(
        "alerts",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
    )
    op.alter_column(
        "alerts",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
    )

    # alert_rules table
    op.alter_column(
        "alert_rules",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
    )
    op.alter_column(
        "alert_rules",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
    )

    # events table
    op.alter_column(
        "events",
        "ended_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=True,
    )
    op.alter_column(
        "events",
        "started_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
    )

    # detections table
    op.alter_column(
        "detections",
        "detected_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
    )

    # logs table
    op.alter_column(
        "logs",
        "timestamp",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
    )

    # gpu_stats table
    op.alter_column(
        "gpu_stats",
        "recorded_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
    )

    # cameras table
    op.alter_column(
        "cameras",
        "last_seen_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=True,
    )
    op.alter_column(
        "cameras",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
    )
