"""add zone anomalies model

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h9
Create Date: 2026-01-21 11:30:00.000000

This migration adds the ZoneAnomaly model for storing detected anomalies
in zone activity patterns. These records track unusual activity that
deviates from learned baselines.

Changes:
- Creates zone_anomalies table
- Adds indexes for efficient querying
- Sets up foreign keys to camera_zones and detections
- Adds check constraints for valid enum values

Implements NEM-3198: Backend Anomaly Detection Service.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6g7h8i9"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = "c3d4e5f6g7h9"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create zone_anomalies table."""

    # =========================================================================
    # CREATE ZONE_ANOMALIES TABLE
    # =========================================================================
    op.create_table(
        "zone_anomalies",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("zone_id", sa.String(), nullable=False),
        sa.Column("camera_id", sa.String(255), nullable=False),
        # Anomaly classification
        sa.Column("anomaly_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="info"),
        # Human-readable details
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # Quantitative details
        sa.Column("expected_value", sa.Float(), nullable=True),
        sa.Column("actual_value", sa.Float(), nullable=True),
        sa.Column("deviation", sa.Float(), nullable=True),
        # Related detection
        sa.Column("detection_id", sa.Integer(), nullable=True),
        sa.Column("thumbnail_url", sa.String(500), nullable=True),
        # Acknowledgment workflow
        sa.Column("acknowledged", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by", sa.String(255), nullable=True),
        # Timestamps
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
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
        # Primary key
        sa.PrimaryKeyConstraint("id"),
        # Foreign keys
        sa.ForeignKeyConstraint(
            ["zone_id"],
            ["camera_zones.id"],
            name="fk_zone_anomalies_zone_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["detection_id"],
            ["detections.id"],
            name="fk_zone_anomalies_detection_id",
            ondelete="SET NULL",
        ),
        # Check constraints
        sa.CheckConstraint(
            "anomaly_type IN ('unusual_time', 'unusual_frequency', 'unusual_dwell', 'unusual_entity')",
            name="ck_zone_anomalies_anomaly_type",
        ),
        sa.CheckConstraint(
            "severity IN ('info', 'warning', 'critical')",
            name="ck_zone_anomalies_severity",
        ),
        sa.CheckConstraint(
            "deviation IS NULL OR deviation >= 0",
            name="ck_zone_anomalies_deviation_non_negative",
        ),
    )

    # =========================================================================
    # CREATE INDEXES
    # =========================================================================
    op.create_index(
        "idx_zone_anomalies_zone_id",
        "zone_anomalies",
        ["zone_id"],
    )
    op.create_index(
        "idx_zone_anomalies_camera_id",
        "zone_anomalies",
        ["camera_id"],
    )
    op.create_index(
        "idx_zone_anomalies_timestamp",
        "zone_anomalies",
        ["timestamp"],
    )
    op.create_index(
        "idx_zone_anomalies_severity",
        "zone_anomalies",
        ["severity"],
    )
    op.create_index(
        "idx_zone_anomalies_acknowledged",
        "zone_anomalies",
        ["acknowledged"],
    )
    op.create_index(
        "idx_zone_anomalies_zone_timestamp",
        "zone_anomalies",
        ["zone_id", "timestamp"],
    )
    op.create_index(
        "idx_zone_anomalies_unacknowledged",
        "zone_anomalies",
        ["acknowledged", "severity", "timestamp"],
    )


def downgrade() -> None:
    """Drop zone_anomalies table."""

    # =========================================================================
    # DROP INDEXES
    # =========================================================================
    op.drop_index(
        "idx_zone_anomalies_unacknowledged",
        table_name="zone_anomalies",
    )
    op.drop_index(
        "idx_zone_anomalies_zone_timestamp",
        table_name="zone_anomalies",
    )
    op.drop_index(
        "idx_zone_anomalies_acknowledged",
        table_name="zone_anomalies",
    )
    op.drop_index(
        "idx_zone_anomalies_severity",
        table_name="zone_anomalies",
    )
    op.drop_index(
        "idx_zone_anomalies_timestamp",
        table_name="zone_anomalies",
    )
    op.drop_index(
        "idx_zone_anomalies_camera_id",
        table_name="zone_anomalies",
    )
    op.drop_index(
        "idx_zone_anomalies_zone_id",
        table_name="zone_anomalies",
    )

    # =========================================================================
    # DROP TABLE
    # =========================================================================
    op.drop_table("zone_anomalies")
