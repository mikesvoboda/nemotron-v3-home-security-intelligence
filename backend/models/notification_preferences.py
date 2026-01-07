"""Notification preferences models for configuring when notifications are sent.

This module defines the data models for managing notification preferences including:
- Global notification settings (enabled, sound, risk filters)
- Per-camera notification settings (enabled, risk threshold)
- Quiet hours periods (time ranges when notifications are muted)

These preferences are used by the notification filter service to determine
whether a notification should be sent for a given event.
"""

from __future__ import annotations

from datetime import time
from enum import StrEnum, auto
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Time,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .camera import Base

if TYPE_CHECKING:
    from .camera import Camera


class RiskLevel(StrEnum):
    """Risk level categories for filtering notifications."""

    CRITICAL = auto()  # 80-100
    HIGH = auto()  # 60-79
    MEDIUM = auto()  # 40-59
    LOW = auto()  # 0-39


class NotificationSound(StrEnum):
    """Available notification sounds."""

    NONE = auto()
    DEFAULT = auto()
    ALERT = auto()
    CHIME = auto()
    URGENT = auto()


class DayOfWeek(StrEnum):
    """Days of the week for quiet hours configuration."""

    MONDAY = auto()
    TUESDAY = auto()
    WEDNESDAY = auto()
    THURSDAY = auto()
    FRIDAY = auto()
    SATURDAY = auto()
    SUNDAY = auto()


class NotificationPreferences(Base):
    """Global notification preferences.

    This is a singleton table (should only have one row with id=1).
    Stores global settings that apply to all notifications.
    """

    __tablename__ = "notification_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    sound: Mapped[str] = mapped_column(String, nullable=False)

    # Risk level filters - which risk levels should trigger notifications
    # Stored as array of risk level strings (e.g., ['critical', 'high'])
    risk_filters: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)

    def __init__(self, **kwargs: object) -> None:
        """Initialize with defaults."""
        super().__init__(**kwargs)
        if not hasattr(self, "id") or self.id is None:
            self.id = 1
        if not hasattr(self, "enabled") or self.enabled is None:
            self.enabled = True
        if not hasattr(self, "sound") or self.sound is None:
            self.sound = NotificationSound.DEFAULT.value
        if not hasattr(self, "risk_filters") or self.risk_filters is None:
            self.risk_filters = [
                RiskLevel.CRITICAL.value,
                RiskLevel.HIGH.value,
                RiskLevel.MEDIUM.value,
            ]

    __table_args__ = (
        CheckConstraint("id = 1", name="ck_notification_preferences_singleton"),
        CheckConstraint(
            f"sound IN ('{NotificationSound.NONE.value}', '{NotificationSound.DEFAULT.value}', "
            f"'{NotificationSound.ALERT.value}', '{NotificationSound.CHIME.value}', "
            f"'{NotificationSound.URGENT.value}')",
            name="ck_notification_preferences_sound",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationPreferences(enabled={self.enabled}, "
            f"sound={self.sound!r}, risk_filters={self.risk_filters})>"
        )


class CameraNotificationSetting(Base):
    """Per-camera notification settings.

    Allows users to configure notification behavior for individual cameras,
    including whether notifications are enabled and the risk threshold.
    """

    __tablename__ = "camera_notification_settings"
    __table_args__ = (
        Index("idx_camera_notification_settings_camera_id", "camera_id", unique=True),
        CheckConstraint(
            "risk_threshold >= 0 AND risk_threshold <= 100",
            name="ck_camera_notification_settings_risk_threshold",
        ),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    camera_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("cameras.id", ondelete="CASCADE"),
        nullable=False,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    risk_threshold: Mapped[int] = mapped_column(Integer, nullable=False)

    def __init__(self, **kwargs: object) -> None:
        """Initialize with defaults."""
        super().__init__(**kwargs)
        if not hasattr(self, "id") or self.id is None:
            self.id = str(uuid4())
        if not hasattr(self, "enabled") or self.enabled is None:
            self.enabled = True
        if not hasattr(self, "risk_threshold") or self.risk_threshold is None:
            self.risk_threshold = 0

    # Relationships
    camera: Mapped[Camera] = relationship("Camera", backref="notification_setting")

    def __repr__(self) -> str:
        return (
            f"<CameraNotificationSetting(camera_id={self.camera_id!r}, "
            f"enabled={self.enabled}, risk_threshold={self.risk_threshold})>"
        )


class QuietHoursPeriod(Base):
    """Quiet hours period when notifications are muted.

    Defines a time range during which notifications should not be sent.
    Can be configured for specific days of the week.
    """

    __tablename__ = "quiet_hours_periods"
    __table_args__ = (
        Index("idx_quiet_hours_periods_start_end", "start_time", "end_time"),
        CheckConstraint(
            "start_time < end_time",
            name="ck_quiet_hours_periods_time_range",
        ),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    label: Mapped[str] = mapped_column(String, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)

    # Days of week when this period is active
    # Stored as array of day strings (e.g., ['monday', 'tuesday'])
    days: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)

    def __init__(self, **kwargs: object) -> None:
        """Initialize with defaults."""
        super().__init__(**kwargs)
        if not hasattr(self, "id") or self.id is None:
            self.id = str(uuid4())
        if not hasattr(self, "days") or self.days is None:
            self.days = [day.value for day in DayOfWeek]

    def __repr__(self) -> str:
        return (
            f"<QuietHoursPeriod(label={self.label!r}, "
            f"start_time={self.start_time}, end_time={self.end_time}, "
            f"days={self.days})>"
        )
