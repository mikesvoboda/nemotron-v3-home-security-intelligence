"""Add backup and webhook tables for NEM-3566 and NEM-3624.

Revision ID: 0004
Revises: 0003
Create Date: 2026-01-25

This migration adds tables for:
- BackupJob: Track background backup job progress and results
- RestoreJob: Track background restore job progress and results
- OutboundWebhook: Configure outbound webhooks to external systems
- WebhookDelivery: Track webhook delivery attempts and retries

Enum types created:
- backup_job_status: pending, running, completed, failed
- restore_job_status: pending, validating, restoring, completed, failed
- webhook_delivery_status: pending, success, failed, retrying
- integration_type: generic, slack, discord, telegram, teams

Related Linear issues: NEM-3566 (Backup/Restore), NEM-3624 (Webhooks)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create backup and webhook tables with supporting enum types."""

    # =========================================================================
    # ENUM TYPES
    # =========================================================================

    # Backup job status enum
    op.execute(
        "CREATE TYPE backup_job_status AS ENUM ('pending', 'running', 'completed', 'failed')"
    )

    # Restore job status enum
    op.execute(
        "CREATE TYPE restore_job_status AS ENUM "
        "('pending', 'validating', 'restoring', 'completed', 'failed')"
    )

    # Webhook delivery status enum
    op.execute(
        "CREATE TYPE webhook_delivery_status AS ENUM ('pending', 'success', 'failed', 'retrying')"
    )

    # Integration type enum
    op.execute(
        "CREATE TYPE integration_type AS ENUM ('generic', 'slack', 'discord', 'telegram', 'teams')"
    )

    # =========================================================================
    # BACKUP TABLES
    # =========================================================================

    # backup_jobs table
    op.create_table(
        "backup_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "running",
                "completed",
                "failed",
                name="backup_job_status",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        # Progress tracking
        sa.Column("total_tables", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("completed_tables", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_step", sa.String(255), nullable=True),
        # Timing
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        # Result
        sa.Column("file_path", sa.String(512), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("manifest_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        # Error
        sa.Column("error_message", sa.Text(), nullable=True),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "progress_percent >= 0 AND progress_percent <= 100",
            name="ck_backup_progress_range",
        ),
    )
    op.create_index("idx_backup_jobs_status", "backup_jobs", ["status"])
    op.create_index("idx_backup_jobs_created_at", "backup_jobs", ["created_at"])

    # restore_jobs table
    op.create_table(
        "restore_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "validating",
                "restoring",
                "completed",
                "failed",
                name="restore_job_status",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        # Source backup info
        sa.Column("backup_id", sa.String(64), nullable=True),
        sa.Column("backup_created_at", sa.DateTime(timezone=True), nullable=True),
        # Progress tracking
        sa.Column("total_tables", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("completed_tables", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_step", sa.String(255), nullable=True),
        # Timing
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        # Result
        sa.Column("items_restored", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        # Error
        sa.Column("error_message", sa.Text(), nullable=True),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "progress_percent >= 0 AND progress_percent <= 100",
            name="ck_restore_progress_range",
        ),
    )
    op.create_index("idx_restore_jobs_status", "restore_jobs", ["status"])
    op.create_index("idx_restore_jobs_created_at", "restore_jobs", ["created_at"])

    # =========================================================================
    # WEBHOOK TABLES
    # =========================================================================

    # outbound_webhooks table
    op.create_table(
        "outbound_webhooks",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("event_types", postgresql.ARRAY(sa.String(50)), nullable=False),
        sa.Column(
            "integration_type",
            postgresql.ENUM(
                "generic",
                "slack",
                "discord",
                "telegram",
                "teams",
                name="integration_type",
                create_type=False,
            ),
            nullable=False,
            server_default="generic",
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        # Auth and headers
        sa.Column("auth_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "custom_headers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("payload_template", sa.Text(), nullable=True),
        # Retry configuration
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("retry_delay_seconds", sa.Integer(), nullable=False, server_default="10"),
        # HMAC signing
        sa.Column("signing_secret", sa.String(64), nullable=True),
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
        # Denormalized stats
        sa.Column("total_deliveries", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("successful_deliveries", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_delivery_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_delivery_status", sa.String(20), nullable=True),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "max_retries >= 0 AND max_retries <= 10",
            name="ck_webhook_max_retries",
        ),
        sa.CheckConstraint(
            "retry_delay_seconds >= 1",
            name="ck_webhook_retry_delay",
        ),
    )
    op.create_index("idx_outbound_webhooks_enabled", "outbound_webhooks", ["enabled"])
    op.create_index(
        "idx_outbound_webhooks_event_types",
        "outbound_webhooks",
        ["event_types"],
        postgresql_using="gin",
    )

    # webhook_deliveries table
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("webhook_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "success",
                "failed",
                "retrying",
                name="webhook_delivery_status",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        # Response info
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        # Request payload for debugging
        sa.Column("request_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        # Retry tracking
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["webhook_id"],
            ["outbound_webhooks.id"],
            name="fk_webhook_deliveries_webhook_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("idx_webhook_deliveries_webhook_id", "webhook_deliveries", ["webhook_id"])
    op.create_index("idx_webhook_deliveries_status", "webhook_deliveries", ["status"])
    op.create_index("idx_webhook_deliveries_created_at", "webhook_deliveries", ["created_at"])
    # Partial index for pending retries
    op.create_index(
        "idx_webhook_deliveries_next_retry",
        "webhook_deliveries",
        ["next_retry_at"],
        postgresql_where=sa.text("status = 'retrying'"),
    )


def downgrade() -> None:
    """Drop backup and webhook tables and enum types."""

    # Drop webhook tables first (child table, then parent)
    op.drop_index("idx_webhook_deliveries_next_retry", table_name="webhook_deliveries")
    op.drop_index("idx_webhook_deliveries_created_at", table_name="webhook_deliveries")
    op.drop_index("idx_webhook_deliveries_status", table_name="webhook_deliveries")
    op.drop_index("idx_webhook_deliveries_webhook_id", table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")

    op.drop_index("idx_outbound_webhooks_event_types", table_name="outbound_webhooks")
    op.drop_index("idx_outbound_webhooks_enabled", table_name="outbound_webhooks")
    op.drop_table("outbound_webhooks")

    # Drop backup tables
    op.drop_index("idx_restore_jobs_created_at", table_name="restore_jobs")
    op.drop_index("idx_restore_jobs_status", table_name="restore_jobs")
    op.drop_table("restore_jobs")

    op.drop_index("idx_backup_jobs_created_at", table_name="backup_jobs")
    op.drop_index("idx_backup_jobs_status", table_name="backup_jobs")
    op.drop_table("backup_jobs")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS integration_type")
    op.execute("DROP TYPE IF EXISTS webhook_delivery_status")
    op.execute("DROP TYPE IF EXISTS restore_job_status")
    op.execute("DROP TYPE IF EXISTS backup_job_status")
