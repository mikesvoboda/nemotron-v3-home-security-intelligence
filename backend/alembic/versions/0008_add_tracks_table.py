"""Add tracks table for storing object track trajectories.

Revision ID: 0008
Revises: 0007
Create Date: 2026-01-26

This migration creates the tracks table for storing object track trajectories.
Tracks represent the movement path of detected objects across video frames,
enabling motion analysis, trajectory prediction, and re-identification.

Table columns:
- id: Primary key (auto-incremented)
- track_id: Track ID from the tracker (unique within a camera session)
- camera_id: Foreign key to the camera that captured this track
- object_class: Detected object class (e.g., 'person', 'car')
- first_seen: Timestamp when the object was first detected
- last_seen: Timestamp when the object was last detected
- trajectory: JSON list of trajectory points [{x, y, timestamp}, ...]
- total_distance: Total distance traveled in pixels (optional)
- avg_speed: Average speed in pixels per second (optional)
- reid_embedding: Re-identification embedding bytes for cross-camera matching

Related feature: Object tracking across video frames for improved event correlation
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the tracks table with indexes for object track storage."""
    # Create the tracks table
    op.create_table(
        "tracks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.Column("camera_id", sa.String(), nullable=False),
        sa.Column("object_class", sa.String(50), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "trajectory",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("total_distance", sa.Float(), nullable=True),
        sa.Column("avg_speed", sa.Float(), nullable=True),
        sa.Column("reid_embedding", sa.LargeBinary(), nullable=True),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["camera_id"],
            ["cameras.id"],
            name="fk_tracks_camera_id",
            ondelete="CASCADE",
        ),
    )

    # Create indexes for efficient querying
    # Index on track_id for fast lookups by track ID
    op.create_index("idx_tracks_track_id", "tracks", ["track_id"])

    # Composite index for looking up tracks by camera and track_id
    op.create_index("idx_tracks_camera_track", "tracks", ["camera_id", "track_id"])

    # Index for time-based queries (e.g., "tracks in the last hour")
    op.create_index("idx_tracks_first_seen", "tracks", ["first_seen"])

    # Index for filtering by object class (e.g., "all person tracks")
    op.create_index("idx_tracks_object_class", "tracks", ["object_class"])

    # Composite index for camera + time range queries
    op.create_index("idx_tracks_camera_first_seen", "tracks", ["camera_id", "first_seen"])


def downgrade() -> None:
    """Drop the tracks table and all its indexes."""
    # Drop indexes first
    op.drop_index("idx_tracks_camera_first_seen", table_name="tracks")
    op.drop_index("idx_tracks_object_class", table_name="tracks")
    op.drop_index("idx_tracks_first_seen", table_name="tracks")
    op.drop_index("idx_tracks_camera_track", table_name="tracks")
    op.drop_index("idx_tracks_track_id", table_name="tracks")

    # Drop the table
    op.drop_table("tracks")
