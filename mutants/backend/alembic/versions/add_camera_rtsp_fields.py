"""Add RTSP/ONVIF streaming fields to cameras table (NEM-4191)

Revision ID: add_camera_rtsp_fields
Revises: add_llm_interactions
Create Date: 2026-01-29 23:30:00.000000

This migration adds fields to support RTSP and ONVIF streaming protocols for
camera ingestion in addition to the existing FTP-based image uploads.

New fields:
- ingestion_mode: How images are acquired (ftp, rtsp, onvif)
- rtsp_url: RTSP stream URL for RTSP/ONVIF cameras
- rtsp_username: Authentication username for RTSP streams
- rtsp_password: Authentication password for RTSP streams (encrypted at rest)
- stream_profile: Which stream profile to use (main, sub, both)
- motion_sensitivity: Motion detection sensitivity (0.0-1.0)
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_camera_rtsp_fields"
down_revision: str | Sequence[str] | None = "add_llm_interactions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add RTSP/ONVIF streaming fields to cameras table."""
    # Add ingestion_mode with default 'ftp' for existing cameras
    op.add_column(
        "cameras",
        sa.Column(
            "ingestion_mode",
            sa.String(),
            nullable=False,
            server_default="ftp",
        ),
    )

    # Add RTSP stream configuration fields (all nullable for FTP cameras)
    op.add_column(
        "cameras",
        sa.Column("rtsp_url", sa.String(), nullable=True),
    )
    op.add_column(
        "cameras",
        sa.Column("rtsp_username", sa.String(), nullable=True),
    )
    op.add_column(
        "cameras",
        sa.Column("rtsp_password", sa.String(), nullable=True),
    )
    op.add_column(
        "cameras",
        sa.Column("stream_profile", sa.String(), nullable=True),
    )

    # Add motion_sensitivity with default 0.5
    op.add_column(
        "cameras",
        sa.Column(
            "motion_sensitivity",
            sa.Float(),
            nullable=False,
            server_default="0.5",
        ),
    )

    # Add CHECK constraint for ingestion_mode enum values
    op.create_check_constraint(
        "ck_cameras_ingestion_mode",
        "cameras",
        "ingestion_mode IN ('ftp', 'rtsp', 'onvif')",
    )

    # Add CHECK constraint for stream_profile enum values
    op.create_check_constraint(
        "ck_cameras_stream_profile",
        "cameras",
        "stream_profile IS NULL OR stream_profile IN ('main', 'sub', 'both')",
    )

    # Add CHECK constraint for motion_sensitivity range
    op.create_check_constraint(
        "ck_cameras_motion_sensitivity",
        "cameras",
        "motion_sensitivity >= 0.0 AND motion_sensitivity <= 1.0",
    )


def downgrade() -> None:
    """Remove RTSP/ONVIF streaming fields from cameras table."""
    # Drop CHECK constraints
    op.drop_constraint("ck_cameras_motion_sensitivity", "cameras", type_="check")
    op.drop_constraint("ck_cameras_stream_profile", "cameras", type_="check")
    op.drop_constraint("ck_cameras_ingestion_mode", "cameras", type_="check")

    # Drop columns in reverse order
    op.drop_column("cameras", "motion_sensitivity")
    op.drop_column("cameras", "stream_profile")
    op.drop_column("cameras", "rtsp_password")
    op.drop_column("cameras", "rtsp_username")
    op.drop_column("cameras", "rtsp_url")
    op.drop_column("cameras", "ingestion_mode")
