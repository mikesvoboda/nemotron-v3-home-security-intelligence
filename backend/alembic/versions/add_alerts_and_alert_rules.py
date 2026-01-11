"""Add alerts and alert_rules tables

Revision ID: add_alerts_rules
Revises: 20251228_fts
Create Date: 2025-12-28 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_alerts_rules"
down_revision: str | Sequence[str] | None = "20251228_fts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create alerts and alert_rules tables."""
    # Create enum types for PostgreSQL
    alert_severity_enum = postgresql.ENUM(
        "low",
        "medium",
        "high",
        "critical",
        name="alert_severity",
        create_type=False,
    )
    alert_status_enum = postgresql.ENUM(
        "pending",
        "delivered",
        "acknowledged",
        "dismissed",
        name="alert_status",
        create_type=False,
    )

    # Create enum types first
    op.execute("CREATE TYPE alert_severity AS ENUM ('low', 'medium', 'high', 'critical')")
    op.execute(
        "CREATE TYPE alert_status AS ENUM ('pending', 'delivered', 'acknowledged', 'dismissed')"
    )

    # Create alert_rules table first (referenced by alerts)
    op.create_table(
        "alert_rules",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, default=True),
        sa.Column(
            "severity",
            alert_severity_enum,
            nullable=False,
            server_default="medium",
        ),
        # Condition fields
        sa.Column("risk_threshold", sa.Integer(), nullable=True),
        sa.Column("object_types", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("camera_ids", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("zone_ids", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("min_confidence", sa.Float(), nullable=True),
        sa.Column("schedule", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        # Legacy conditions field
        sa.Column("conditions", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        # Dedup and cooldown
        sa.Column(
            "dedup_key_template",
            sa.String(length=255),
            nullable=False,
            server_default="{camera_id}:{rule_id}",
        ),
        sa.Column("cooldown_seconds", sa.Integer(), nullable=False, default=300),
        # Channels
        sa.Column("channels", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for alert_rules
    op.create_index("idx_alert_rules_name", "alert_rules", ["name"], unique=False)
    op.create_index("idx_alert_rules_enabled", "alert_rules", ["enabled"], unique=False)
    op.create_index("idx_alert_rules_severity", "alert_rules", ["severity"], unique=False)

    # Create alerts table
    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("rule_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column(
            "severity",
            alert_severity_enum,
            nullable=False,
            server_default="medium",
        ),
        sa.Column(
            "status",
            alert_status_enum,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("channels", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("dedup_key", sa.String(length=255), nullable=False),
        sa.Column("metadata", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name="fk_alerts_event_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["rule_id"],
            ["alert_rules.id"],
            name="fk_alerts_rule_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for alerts
    op.create_index("idx_alerts_event_id", "alerts", ["event_id"], unique=False)
    op.create_index("idx_alerts_rule_id", "alerts", ["rule_id"], unique=False)
    op.create_index("idx_alerts_severity", "alerts", ["severity"], unique=False)
    op.create_index("idx_alerts_status", "alerts", ["status"], unique=False)
    op.create_index("idx_alerts_created_at", "alerts", ["created_at"], unique=False)
    op.create_index("idx_alerts_dedup_key", "alerts", ["dedup_key"], unique=False)
    op.create_index(
        "idx_alerts_dedup_key_created_at",
        "alerts",
        ["dedup_key", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop alerts and alert_rules tables."""
    # Drop indexes for alerts
    op.drop_index("idx_alerts_dedup_key_created_at", table_name="alerts", if_exists=True)
    op.drop_index("idx_alerts_dedup_key", table_name="alerts", if_exists=True)
    op.drop_index("idx_alerts_created_at", table_name="alerts", if_exists=True)
    op.drop_index("idx_alerts_status", table_name="alerts", if_exists=True)
    op.drop_index("idx_alerts_severity", table_name="alerts", if_exists=True)
    op.drop_index("idx_alerts_rule_id", table_name="alerts", if_exists=True)
    op.drop_index("idx_alerts_event_id", table_name="alerts", if_exists=True)

    # Drop alerts table
    op.drop_table("alerts")

    # Drop indexes for alert_rules
    op.drop_index("idx_alert_rules_severity", table_name="alert_rules", if_exists=True)
    op.drop_index("idx_alert_rules_enabled", table_name="alert_rules", if_exists=True)
    op.drop_index("idx_alert_rules_name", table_name="alert_rules", if_exists=True)

    # Drop alert_rules table
    op.drop_table("alert_rules")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS alert_status")
    op.execute("DROP TYPE IF EXISTS alert_severity")
