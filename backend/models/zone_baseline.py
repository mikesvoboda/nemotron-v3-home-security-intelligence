"""Zone activity baseline model for statistical tracking.

This module defines the SQLAlchemy model for storing zone activity baselines
used to detect anomalies by comparing real-time activity against historical norms.

Features:
    - Hourly activity statistics (mean, std dev, min, max)
    - Day-of-week bucketing for pattern recognition
    - Class-specific baselines (person, vehicle, etc.)
    - Configurable learning period
    - Automatic staleness detection

Related: NEM-3197 (Backend Zone Baseline Service)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.time_utils import utc_now

from .camera import Base

if TYPE_CHECKING:
    from .camera_zone import CameraZone


class ZoneActivityBaseline(Base):
    """Zone activity baseline for storing historical activity patterns.

    Stores statistical summaries of zone activity aggregated by:
    - Hour of day (0-23)
    - Day of week (0=Monday, 6=Sunday)
    - Detection class (person, vehicle, etc.)

    These baselines are used to detect anomalies when real-time activity
    deviates significantly from expected patterns.

    Attributes:
        id: Primary key (string format like camera zones).
        zone_id: Foreign key to the camera zone.
        camera_id: Camera ID for quick reference (denormalized).
        hour_of_day: Hour bucket (0-23).
        day_of_week: Day bucket (0=Monday through 6=Sunday).
        detection_class: Class of detection (person, vehicle, etc.).
        sample_count: Number of samples in this baseline.
        mean_count: Average activity count for this time bucket.
        std_dev: Standard deviation of activity count.
        min_count: Minimum observed count.
        max_count: Maximum observed count.
        last_updated: When this baseline was last computed.
        created_at: Record creation timestamp.

    Related: NEM-3197
    """

    __tablename__ = "zone_activity_baselines"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    zone_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("camera_zones.id", ondelete="CASCADE"),
        nullable=False,
    )
    camera_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Time bucketing
    hour_of_day: Mapped[int] = mapped_column(Integer, nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)

    # Detection class
    detection_class: Mapped[str] = mapped_column(String(50), nullable=False, default="all")

    # Statistical values
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mean_count: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    std_dev: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    min_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Timestamps
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    zone: Mapped[CameraZone] = relationship("CameraZone", back_populates="activity_baseline")

    # Constraints and indexes
    __table_args__ = (
        Index("idx_zone_baselines_zone_id", "zone_id"),
        Index("idx_zone_baselines_camera_id", "camera_id"),
        Index("idx_zone_baselines_time_bucket", "zone_id", "hour_of_day", "day_of_week"),
        Index(
            "idx_zone_baselines_lookup",
            "zone_id",
            "hour_of_day",
            "day_of_week",
            "detection_class",
        ),
        CheckConstraint("hour_of_day >= 0 AND hour_of_day <= 23", name="ck_baseline_hour"),
        CheckConstraint("day_of_week >= 0 AND day_of_week <= 6", name="ck_baseline_day_of_week"),
        CheckConstraint("sample_count >= 0", name="ck_baseline_sample_count"),
        CheckConstraint("std_dev >= 0", name="ck_baseline_std_dev"),
        CheckConstraint("min_count >= 0", name="ck_baseline_min_count"),
        CheckConstraint("max_count >= min_count", name="ck_baseline_max_gte_min"),
    )

    def __repr__(self) -> str:
        return (
            f"<ZoneActivityBaseline(id={self.id!r}, zone_id={self.zone_id!r}, "
            f"hour={self.hour_of_day}, day={self.day_of_week}, "
            f"class={self.detection_class!r}, mean={self.mean_count:.2f})>"
        )

    def is_stale(self, max_age_hours: int = 168) -> bool:
        """Check if the baseline is stale (default: 7 days).

        Args:
            max_age_hours: Maximum age in hours before considered stale.

        Returns:
            True if the baseline is older than max_age_hours.
        """
        from datetime import timedelta

        age = utc_now() - self.last_updated
        return age > timedelta(hours=max_age_hours)

    def deviation_from_mean(self, observed: float) -> float:
        """Calculate standard deviations from mean.

        Args:
            observed: The observed activity count.

        Returns:
            Number of standard deviations from the mean.
            Returns 0 if std_dev is 0 (no variation in baseline).
        """
        if self.std_dev == 0:
            return 0.0
        return abs(observed - self.mean_count) / self.std_dev
