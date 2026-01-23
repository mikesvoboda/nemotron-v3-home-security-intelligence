"""Zone activity baseline model for statistical tracking.

This module defines the SQLAlchemy model for storing zone activity baselines
used to detect anomalies by comparing real-time activity against historical norms.

Features:
    - Hourly activity patterns (24 values, one per hour)
    - Daily activity patterns (7 values, Monday-Sunday)
    - Entity class distribution (JSONB)
    - Statistical metrics for daily counts
    - Crossing rate and dwell time statistics
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
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.time_utils import utc_now

from .camera import Base

if TYPE_CHECKING:
    from .camera_zone import CameraZone


class ZoneActivityBaseline(Base):
    """Zone activity baseline for storing historical activity patterns.

    Stores statistical summaries of zone activity as aggregated patterns:
    - Hourly pattern: 24 values representing typical activity per hour
    - Daily pattern: 7 values representing typical activity per day of week
    - Entity class distribution: JSONB with counts per detection class

    These baselines are used to detect anomalies when real-time activity
    deviates significantly from expected patterns.

    Attributes:
        id: Primary key (UUID, auto-generated).
        zone_id: Foreign key to the camera zone (unique - one baseline per zone).
        camera_id: Camera ID for quick reference (denormalized).
        hourly_pattern: Array of 24 floats for hourly activity patterns.
        hourly_std: Array of 24 floats for hourly standard deviations.
        daily_pattern: Array of 7 floats for day-of-week patterns (0=Monday).
        daily_std: Array of 7 floats for day-of-week standard deviations.
        entity_class_distribution: JSONB with detection class counts.
        mean_daily_count: Average daily activity count.
        std_daily_count: Standard deviation of daily count.
        min_daily_count: Minimum observed daily count.
        max_daily_count: Maximum observed daily count.
        typical_crossing_rate: Typical zone crossing rate per hour.
        typical_crossing_std: Standard deviation of crossing rate.
        typical_dwell_time: Typical dwell time in seconds.
        typical_dwell_std: Standard deviation of dwell time.
        sample_count: Number of days/samples in this baseline.
        last_updated: When this baseline was last computed.
        created_at: Record creation timestamp.
        updated_at: Record update timestamp.

    Related: NEM-3197
    """

    __tablename__ = "zone_activity_baselines"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default="gen_random_uuid()",
    )
    zone_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("camera_zones.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    camera_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Hourly pattern: 24 values (one per hour)
    hourly_pattern: Mapped[list[float]] = mapped_column(
        ARRAY(Float),
        nullable=False,
        default=list,
        server_default="{}",
    )
    hourly_std: Mapped[list[float]] = mapped_column(
        ARRAY(Float),
        nullable=False,
        default=list,
        server_default="{}",
    )

    # Daily pattern: 7 values (Monday=0 to Sunday=6)
    daily_pattern: Mapped[list[float]] = mapped_column(
        ARRAY(Float),
        nullable=False,
        default=list,
        server_default="{}",
    )
    daily_std: Mapped[list[float]] = mapped_column(
        ARRAY(Float),
        nullable=False,
        default=list,
        server_default="{}",
    )

    # Entity class distribution (JSONB)
    entity_class_distribution: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    # Statistical metrics for daily counts
    mean_daily_count: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0.0"
    )
    std_daily_count: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0.0"
    )
    min_daily_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    max_daily_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    # Crossing rate statistics (per hour)
    typical_crossing_rate: Mapped[float] = mapped_column(
        Float, nullable=False, default=10.0, server_default="10.0"
    )
    typical_crossing_std: Mapped[float] = mapped_column(
        Float, nullable=False, default=5.0, server_default="5.0"
    )

    # Dwell time statistics (in seconds)
    typical_dwell_time: Mapped[float] = mapped_column(
        Float, nullable=False, default=30.0, server_default="30.0"
    )
    typical_dwell_std: Mapped[float] = mapped_column(
        Float, nullable=False, default=10.0, server_default="10.0"
    )

    # Sample info
    sample_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    # Timestamps
    last_updated: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, server_default="now()"
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, onupdate=utc_now, nullable=True
    )

    # Relationships
    zone: Mapped[CameraZone] = relationship("CameraZone", back_populates="activity_baseline")

    # Constraints and indexes
    __table_args__ = (
        Index("idx_zone_activity_baselines_zone_id", "zone_id"),
        Index("idx_zone_activity_baselines_camera_id", "camera_id"),
        Index("idx_zone_activity_baselines_last_updated", "last_updated"),
        UniqueConstraint("zone_id", name="uq_zone_activity_baselines_zone_id"),
        CheckConstraint("sample_count >= 0", name="ck_baseline_sample_count"),
        CheckConstraint("std_daily_count >= 0", name="ck_baseline_std_daily_count"),
        CheckConstraint("min_daily_count >= 0", name="ck_baseline_min_daily_count"),
        CheckConstraint("max_daily_count >= min_daily_count", name="ck_baseline_max_gte_min_daily"),
        CheckConstraint("typical_crossing_std >= 0", name="ck_baseline_crossing_std"),
        CheckConstraint("typical_dwell_std >= 0", name="ck_baseline_dwell_std"),
    )

    def __repr__(self) -> str:
        return (
            f"<ZoneActivityBaseline(id={self.id!r}, zone_id={self.zone_id!r}, "
            f"sample_count={self.sample_count}, mean_daily={self.mean_daily_count:.2f})>"
        )

    def is_stale(self, max_age_hours: int = 168) -> bool:
        """Check if the baseline is stale (default: 7 days).

        Args:
            max_age_hours: Maximum age in hours before considered stale.

        Returns:
            True if the baseline is older than max_age_hours.
        """
        from datetime import timedelta

        if self.last_updated is None:
            return True
        age = utc_now() - self.last_updated
        return age > timedelta(hours=max_age_hours)

    def get_expected_activity(self, hour: int, day_of_week: int) -> float:
        """Get expected activity for a given time.

        Args:
            hour: Hour of day (0-23).
            day_of_week: Day of week (0=Monday through 6=Sunday).

        Returns:
            Expected activity level combining hourly and daily patterns.
        """
        hourly = self.hourly_pattern[hour] if len(self.hourly_pattern) > hour else 0.0
        daily = self.daily_pattern[day_of_week] if len(self.daily_pattern) > day_of_week else 1.0
        # Combine patterns (hourly pattern scaled by daily factor)
        return (
            hourly * (daily / max(sum(self.daily_pattern) / 7, 1.0))
            if self.daily_pattern
            else hourly
        )

    def deviation_from_expected(self, observed: float, hour: int, day_of_week: int) -> float:
        """Calculate standard deviations from expected activity.

        Args:
            observed: The observed activity count.
            hour: Hour of day (0-23).
            day_of_week: Day of week (0=Monday through 6=Sunday).

        Returns:
            Number of standard deviations from the expected value.
            Returns 0 if std is 0 (no variation in baseline).
        """
        expected = self.get_expected_activity(hour, day_of_week)
        hourly_std = self.hourly_std[hour] if len(self.hourly_std) > hour else 0.0
        if hourly_std == 0:
            return 0.0
        return abs(observed - expected) / hourly_std
