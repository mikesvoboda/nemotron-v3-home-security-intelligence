"""Track model for storing object track trajectories.

Tracks represent the movement path of detected objects across video frames,
enabling motion analysis, trajectory prediction, and re-identification.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, LargeBinary, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .camera import Base

if TYPE_CHECKING:
    from .camera import Camera


class Track(Base):
    """Track model for storing object track trajectories.

    A track represents the movement path of a single detected object
    across multiple video frames. Tracks are created by the object
    tracker (e.g., ByteTrack, BoT-SORT) and contain:

    - Temporal bounds (first_seen, last_seen)
    - Trajectory data (list of {x, y, timestamp} points)
    - Motion statistics (total_distance, avg_speed)
    - Optional re-identification embedding for cross-camera tracking

    Attributes:
        id: Primary key (auto-incremented)
        track_id: Track ID from the tracker (unique within a camera session)
        camera_id: Foreign key to the camera that captured this track
        object_class: Detected object class (e.g., 'person', 'car')
        first_seen: Timestamp when the object was first detected
        last_seen: Timestamp when the object was last detected
        trajectory: JSON list of trajectory points [{x, y, timestamp}, ...]
        total_distance: Total distance traveled in pixels (optional)
        avg_speed: Average speed in pixels per second (optional)
        reid_embedding: Re-identification embedding bytes for cross-camera matching
    """

    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    track_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    camera_id: Mapped[str] = mapped_column(
        String, ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False
    )
    object_class: Mapped[str] = mapped_column(String(50), nullable=False)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Trajectory: list of {x: float, y: float, timestamp: str/datetime} points
    trajectory: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    total_distance: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Re-identification embedding for cross-camera matching (optional)
    # Stored as raw bytes; typically a 256-512 dimensional float32 vector
    reid_embedding: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    # Relationships
    camera: Mapped[Camera] = relationship("Camera", back_populates="tracks")

    # Indexes for efficient querying
    __table_args__ = (
        # Composite index for looking up tracks by camera and track_id
        Index("idx_tracks_camera_track", "camera_id", "track_id"),
        # Index for time-based queries (e.g., "tracks in the last hour")
        Index("idx_tracks_first_seen", "first_seen"),
        # Index for filtering by object class (e.g., "all person tracks")
        Index("idx_tracks_object_class", "object_class"),
        # Composite index for camera + time range queries
        Index("idx_tracks_camera_first_seen", "camera_id", "first_seen"),
    )

    def __repr__(self) -> str:
        return (
            f"<Track(id={self.id}, track_id={self.track_id}, "
            f"camera_id={self.camera_id!r}, object_class={self.object_class!r})>"
        )
