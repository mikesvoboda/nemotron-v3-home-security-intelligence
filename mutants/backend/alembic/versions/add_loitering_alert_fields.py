"""Add loitering detection alert fields

Revision ID: add_loitering_alert_fields
Revises: add_camera_rtsp_fields
Create Date: 2026-02-01 12:00:00.000000

This migration adds fields to support loitering (dwell time) detection alerts:

1. polygon_zones table:
   - loitering_threshold_seconds: Change type from INTEGER to FLOAT
   - Default changed from 300 to 60.0 seconds for faster loitering detection

2. alert_rules table:
   - dwell_time_enabled: Enable loitering detection for the rule
     When enabled, alerts are triggered when an object remains in a zone
     longer than the zone's loitering_threshold_seconds
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_loitering_alert_fields"
down_revision: str | Sequence[str] | None = "add_camera_rtsp_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add loitering detection fields."""
    # Change loitering_threshold_seconds from INTEGER to FLOAT in polygon_zones
    # Using USING clause to cast existing INTEGER values to FLOAT
    op.alter_column(
        "polygon_zones",
        "loitering_threshold_seconds",
        existing_type=sa.Integer(),
        type_=sa.Float(),
        existing_nullable=False,
        postgresql_using="loitering_threshold_seconds::float",
    )

    # Update the default value from 300 to 60.0
    op.alter_column(
        "polygon_zones",
        "loitering_threshold_seconds",
        existing_type=sa.Float(),
        server_default="60.0",
        existing_nullable=False,
    )

    # Add dwell_time_enabled column to alert_rules
    op.add_column(
        "alert_rules",
        sa.Column(
            "dwell_time_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    """Remove loitering detection fields."""
    # Drop dwell_time_enabled column from alert_rules
    op.drop_column("alert_rules", "dwell_time_enabled")

    # Revert loitering_threshold_seconds default back to 300
    op.alter_column(
        "polygon_zones",
        "loitering_threshold_seconds",
        existing_type=sa.Float(),
        server_default="300",
        existing_nullable=False,
    )

    # Change loitering_threshold_seconds back from FLOAT to INTEGER
    # Using USING clause to cast FLOAT values to INTEGER (truncates decimals)
    op.alter_column(
        "polygon_zones",
        "loitering_threshold_seconds",
        existing_type=sa.Float(),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using="loitering_threshold_seconds::integer",
    )
