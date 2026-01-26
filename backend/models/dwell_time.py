"""Dwell time record model for tracking object presence in zones.

This module provides the DwellTimeRecord model for tracking how long objects
stay within polygon zones. It supports loitering detection by recording entry/exit
times and calculating total dwell time for each tracked object.

The model integrates with PolygonZone for zone-based monitoring and supports
configurable loitering thresholds per zone.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.time_utils import utc_now

from .camera import Base

if TYPE_CHECKING:
    from .analytics_zone import PolygonZone
    from .camera import Camera


class DwellTimeRecord(Base):
    """Record of an object's dwell time within a polygon zone.

    A DwellTimeRecord tracks a single object's presence in a zone from entry
    to exit. It captures the entry time, exit time (if known), and calculated
    total dwell duration. This enables loitering detection by identifying
    objects that exceed configured time thresholds.

    Attributes:
        id: Unique identifier for the dwell time record
        zone_id: Foreign key to the polygon zone being monitored
        track_id: Object tracking ID from the detection pipeline
        camera_id: Foreign key to the camera where detection occurred
        object_class: Classification of the detected object (e.g., "person")
        entry_time: Timestamp when the object entered the zone
        exit_time: Timestamp when the object exited (None if still present)
        total_seconds: Calculated dwell time in seconds
        triggered_alert: Whether this dwell time triggered a loitering alert

    Example:
        # Record entry into a zone
        record = DwellTimeRecord(
            zone_id=1,
            track_id=42,
            camera_id="front_door",
            object_class="person",
            entry_time=datetime.now(UTC),
            total_seconds=0.0,
            triggered_alert=False,
        )

        # Update on exit
        record.exit_time = datetime.now(UTC)
        record.total_seconds = (record.exit_time - record.entry_time).total_seconds()
    """

    __tablename__ = "dwell_time_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    zone_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("polygon_zones.id", ondelete="CASCADE"),
        nullable=False,
    )
    track_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    camera_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("cameras.id", ondelete="CASCADE"),
        nullable=False,
    )
    object_class: Mapped[str] = mapped_column(String(50), nullable=False)
    entry_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    exit_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    total_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    triggered_alert: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    zone: Mapped[PolygonZone] = relationship("PolygonZone", back_populates="dwell_time_records")
    camera: Mapped[Camera] = relationship("Camera", back_populates="dwell_time_records")

    __table_args__ = (
        Index("idx_dwell_time_zone", "zone_id"),
        Index("idx_dwell_time_camera", "camera_id"),
        Index("idx_dwell_time_entry", "entry_time"),
        Index("idx_dwell_time_zone_track", "zone_id", "track_id"),
        Index("idx_dwell_time_active", "zone_id", "exit_time"),
    )

    def __repr__(self) -> str:
        return (
            f"<DwellTimeRecord(id={self.id!r}, zone_id={self.zone_id}, "
            f"track_id={self.track_id}, total_seconds={self.total_seconds:.1f}, "
            f"triggered_alert={self.triggered_alert})>"
        )

    @property
    def is_active(self) -> bool:
        """Check if the object is still in the zone (no exit time recorded)."""
        return self.exit_time is None

    def calculate_dwell_time(self, current_time: datetime | None = None) -> float:
        """Calculate current dwell time in seconds.

        Args:
            current_time: Time to calculate dwell from. If None, uses utc_now().

        Returns:
            Dwell time in seconds from entry to exit_time or current_time.
        """
        end_time = self.exit_time or current_time or utc_now()
        return (end_time - self.entry_time).total_seconds()
