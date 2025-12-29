"""Baseline activity models for anomaly detection.

This module defines SQLAlchemy models for tracking baseline activity patterns
per camera and per detection class. These models support anomaly detection
by comparing current activity against historical baselines.

Features:
    - Per-camera activity rates by hour and day-of-week
    - Per-class frequency tracking (e.g., "vehicles after midnight are rare")
    - Rolling window support with exponential decay
    - Lightweight SQL-based aggregation

Models:
    - ActivityBaseline: Tracks overall activity rate per camera by time slot
    - ClassBaseline: Tracks frequency of specific object classes per camera
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .camera import Base

if TYPE_CHECKING:
    from .camera import Camera


class ActivityBaseline(Base):
    """Baseline activity model for tracking activity rates.

    Tracks average activity counts per camera for each hour-of-day and
    day-of-week combination. Uses exponential decay to handle seasonal drift
    with a 30-day rolling window.

    Attributes:
        id: Primary key.
        camera_id: Foreign key to the camera.
        hour: Hour of day (0-23).
        day_of_week: Day of week (0=Monday, 6=Sunday).
        avg_count: Exponentially weighted moving average of activity count.
        sample_count: Number of samples used to calculate the average.
        last_updated: Timestamp of last update.
    """

    __tablename__ = "activity_baselines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[str] = mapped_column(
        String, ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False
    )
    hour: Mapped[int] = mapped_column(Integer, nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_count: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    camera: Mapped[Camera] = relationship("Camera", backref="activity_baselines")

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("camera_id", "hour", "day_of_week", name="uq_activity_baseline_slot"),
        Index("idx_activity_baseline_camera", "camera_id"),
        Index("idx_activity_baseline_slot", "camera_id", "hour", "day_of_week"),
    )

    def __repr__(self) -> str:
        return (
            f"<ActivityBaseline(camera_id={self.camera_id!r}, "
            f"hour={self.hour}, day_of_week={self.day_of_week}, "
            f"avg_count={self.avg_count:.2f})>"
        )


class ClassBaseline(Base):
    """Baseline model for tracking detection class frequency.

    Tracks the frequency of specific object classes (e.g., person, vehicle, animal)
    per camera and hour-of-day. Uses exponential decay for seasonal drift handling.

    Attributes:
        id: Primary key.
        camera_id: Foreign key to the camera.
        detection_class: The object class (e.g., "person", "vehicle").
        hour: Hour of day (0-23).
        frequency: Exponentially weighted moving average of class frequency.
        sample_count: Number of samples used to calculate the frequency.
        last_updated: Timestamp of last update.
    """

    __tablename__ = "class_baselines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[str] = mapped_column(
        String, ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False
    )
    detection_class: Mapped[str] = mapped_column(String, nullable=False)
    hour: Mapped[int] = mapped_column(Integer, nullable=False)
    frequency: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    camera: Mapped[Camera] = relationship("Camera", backref="class_baselines")

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("camera_id", "detection_class", "hour", name="uq_class_baseline_slot"),
        Index("idx_class_baseline_camera", "camera_id"),
        Index("idx_class_baseline_class", "camera_id", "detection_class"),
        Index("idx_class_baseline_slot", "camera_id", "detection_class", "hour"),
    )

    def __repr__(self) -> str:
        return (
            f"<ClassBaseline(camera_id={self.camera_id!r}, "
            f"detection_class={self.detection_class!r}, hour={self.hour}, "
            f"frequency={self.frequency:.4f})>"
        )
