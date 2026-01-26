"""HeatmapData model for movement heatmap visualization.

This module provides the HeatmapData model for storing aggregated heatmap data
that visualizes activity patterns over time. Heatmaps are generated from detection
positions and stored at different resolutions (hourly, daily, weekly).

The data field stores compressed numpy arrays representing accumulated detection
positions on a grid, which can be rendered as colored heatmap images.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .camera import Base

if TYPE_CHECKING:
    from .camera import Camera


class HeatmapResolution(StrEnum):
    """Resolution levels for heatmap data aggregation.

    Attributes:
        HOURLY: Aggregate detections by hour.
        DAILY: Aggregate detections by day.
        WEEKLY: Aggregate detections by week.
    """

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


class HeatmapData(Base):
    """Model for storing aggregated heatmap data.

    Stores compressed numpy arrays representing detection positions over time,
    allowing visualization of activity patterns per camera at different
    time resolutions.

    Attributes:
        id: Primary key.
        camera_id: Foreign key to cameras table.
        time_bucket: Start time of the aggregation period (hour/day/week start).
        resolution: Aggregation resolution (hourly, daily, weekly).
        width: Width of the heatmap grid.
        height: Height of the heatmap grid.
        data: Compressed numpy array of accumulated detection counts per cell.
        total_detections: Total number of detections in this time bucket.
        created_at: When this record was created.
        updated_at: When this record was last updated.

    Example:
        heatmap = HeatmapData(
            camera_id="front_door",
            time_bucket=datetime(2026, 1, 26, 10, 0, 0, tzinfo=UTC),
            resolution=HeatmapResolution.HOURLY,
            width=64,
            height=48,
            data=compressed_array,
            total_detections=150,
        )
    """

    __tablename__ = "heatmap_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("cameras.id", ondelete="CASCADE"),
        nullable=False,
    )
    time_bucket: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Start time of aggregation period (hour/day/week start)",
    )
    resolution: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Aggregation resolution: hourly, daily, weekly",
    )
    width: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Width of heatmap grid in pixels",
    )
    height: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Height of heatmap grid in pixels",
    )
    data: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
        comment="Compressed numpy array of detection counts per grid cell",
    )
    total_detections: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total detections in this time bucket",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    camera: Mapped[Camera] = relationship("Camera", lazy="selectin")  # type: ignore[name-defined]

    # Indexes and constraints
    __table_args__ = (
        # Unique constraint: one heatmap per camera, time bucket, and resolution
        Index(
            "ix_heatmap_data_camera_time_resolution",
            "camera_id",
            "time_bucket",
            "resolution",
            unique=True,
        ),
        # Index for querying by camera and time range
        Index("ix_heatmap_data_camera_time", "camera_id", "time_bucket"),
        # Index for querying by resolution
        Index("ix_heatmap_data_resolution", "resolution"),
        # BRIN index for time-series queries (efficient for chronological data)
        Index(
            "ix_heatmap_data_time_brin",
            "time_bucket",
            postgresql_using="brin",
        ),
        # Check constraints for valid values
        CheckConstraint(
            "resolution IN ('hourly', 'daily', 'weekly')",
            name="ck_heatmap_data_resolution_valid",
        ),
        CheckConstraint(
            "width > 0",
            name="ck_heatmap_data_width_positive",
        ),
        CheckConstraint(
            "height > 0",
            name="ck_heatmap_data_height_positive",
        ),
        CheckConstraint(
            "total_detections >= 0",
            name="ck_heatmap_data_detections_non_negative",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<HeatmapData(id={self.id}, camera_id={self.camera_id!r}, "
            f"time_bucket={self.time_bucket}, resolution={self.resolution!r}, "
            f"total_detections={self.total_detections})>"
        )
