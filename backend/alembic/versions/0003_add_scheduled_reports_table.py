"""Add scheduled_reports table (NEM-3621).

Revision ID: 0003
Revises: 0002
Create Date: 2026-01-25

This migration creates the scheduled_reports table for managing
scheduled reports. The table supports:

- Report frequency: daily, weekly, monthly
- Schedule configuration: hour, minute, day of week (0-6), day of month (1-31), timezone
- Output format: pdf, csv, json
- Email recipients stored as PostgreSQL array
- Report content options: include_charts, include_event_details
- Tracking of last and next run times
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create scheduled_reports table."""
    # Create report_frequency enum
    report_frequency_enum = sa.Enum(
        "daily",
        "weekly",
        "monthly",
        name="report_frequency",
    )
    report_frequency_enum.create(op.get_bind(), checkfirst=True)

    # Create report_format enum
    report_format_enum = sa.Enum(
        "pdf",
        "csv",
        "json",
        name="report_format",
    )
    report_format_enum.create(op.get_bind(), checkfirst=True)

    # Create scheduled_reports table
    op.create_table(
        "scheduled_reports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("frequency", report_frequency_enum, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        # Schedule configuration
        sa.Column("day_of_week", sa.Integer(), nullable=True),
        sa.Column("day_of_month", sa.Integer(), nullable=True),
        sa.Column("hour", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("minute", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("timezone", sa.String(50), nullable=False, server_default="'UTC'"),
        # Output format
        sa.Column("format", report_format_enum, nullable=False, server_default="'pdf'"),
        # Email recipients (PostgreSQL array)
        sa.Column("email_recipients", postgresql.ARRAY(sa.String()), nullable=True),
        # Report content options
        sa.Column("include_charts", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("include_event_details", sa.Boolean(), nullable=False, server_default="true"),
        # Run tracking
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # CHECK constraints
        sa.CheckConstraint(
            "day_of_week IS NULL OR (day_of_week >= 0 AND day_of_week <= 6)",
            name="ck_scheduled_reports_day_of_week_range",
        ),
        sa.CheckConstraint(
            "day_of_month IS NULL OR (day_of_month >= 1 AND day_of_month <= 31)",
            name="ck_scheduled_reports_day_of_month_range",
        ),
        sa.CheckConstraint(
            "hour >= 0 AND hour <= 23",
            name="ck_scheduled_reports_hour_range",
        ),
        sa.CheckConstraint(
            "minute >= 0 AND minute <= 59",
            name="ck_scheduled_reports_minute_range",
        ),
    )

    # Create indexes
    op.create_index(
        "idx_scheduled_reports_enabled",
        "scheduled_reports",
        ["enabled"],
    )
    op.create_index(
        "idx_scheduled_reports_frequency",
        "scheduled_reports",
        ["frequency"],
    )
    op.create_index(
        "idx_scheduled_reports_next_run_at",
        "scheduled_reports",
        ["next_run_at"],
    )
    op.create_index(
        "idx_scheduled_reports_enabled_next_run",
        "scheduled_reports",
        ["enabled", "next_run_at"],
    )


def downgrade() -> None:
    """Drop scheduled_reports table."""
    # Drop indexes
    op.drop_index("idx_scheduled_reports_enabled_next_run", table_name="scheduled_reports")
    op.drop_index("idx_scheduled_reports_next_run_at", table_name="scheduled_reports")
    op.drop_index("idx_scheduled_reports_frequency", table_name="scheduled_reports")
    op.drop_index("idx_scheduled_reports_enabled", table_name="scheduled_reports")

    # Drop table
    op.drop_table("scheduled_reports")

    # Drop enum types
    sa.Enum(name="report_format").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="report_frequency").drop(op.get_bind(), checkfirst=True)
