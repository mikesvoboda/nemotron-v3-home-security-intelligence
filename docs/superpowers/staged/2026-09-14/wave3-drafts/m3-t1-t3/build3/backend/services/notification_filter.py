"""Notification filter service for determining when to send notifications.

This service checks notification preferences to determine whether a notification
should be sent for a given event. It considers:
- Global notification preferences (enabled/disabled, risk filters)
- Per-camera notification settings (enabled/disabled, risk threshold)
- Quiet hours periods (time ranges when notifications are muted)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from backend.models.notification_preferences import RiskLevel

if TYPE_CHECKING:
    from backend.models.notification_preferences import (
        CameraNotificationSetting,
        NotificationPreferences,
        QuietHoursPeriod,
    )


class NotificationFilterService:
    """Service for filtering notifications based on user preferences."""

    def should_notify(
        self,
        risk_score: int,
        camera_id: str,  # noqa: ARG002
        timestamp: datetime,
        global_prefs: NotificationPreferences,
        camera_setting: CameraNotificationSetting | None = None,
        quiet_periods: list[QuietHoursPeriod] | None = None,
    ) -> bool:
        """Determine if a notification should be sent.

        Args:
            risk_score: Event risk score (0-100)
            camera_id: Camera ID
            timestamp: Event timestamp
            global_prefs: Global notification preferences
            camera_setting: Per-camera notification setting (optional)
            quiet_periods: List of quiet hours periods (optional)

        Returns:
            True if notification should be sent, False otherwise
        """
        # Check if notifications are globally enabled
        if not global_prefs.enabled:
            return False

        # Check if risk level is in enabled filters
        risk_level = self._risk_score_to_level(risk_score)
        if risk_level.value not in global_prefs.risk_filters:
            return False

        # Check per-camera settings if provided
        if camera_setting is not None:
            # Check if camera notifications are enabled
            if not camera_setting.enabled:
                return False

            # Check if risk score meets camera threshold
            if risk_score < camera_setting.risk_threshold:
                return False

        # Check quiet hours if provided
        if quiet_periods:
            for period in quiet_periods:
                if self.is_quiet_period(timestamp, period):
                    return False

        return True

    def is_quiet_period(self, timestamp: datetime, period: QuietHoursPeriod) -> bool:
        """Check if a timestamp falls within a quiet hours period.

        Args:
            timestamp: Timestamp to check
            period: Quiet hours period

        Returns:
            True if timestamp is during quiet hours, False otherwise
        """
        # Check if day of week matches
        day_name = timestamp.strftime("%A").lower()  # e.g., "monday"
        if day_name not in period.days:
            return False

        # Check if time is within range
        current_time = timestamp.time()

        # Handle periods that span midnight (e.g., 22:00 to 06:00)
        if period.start_time > period.end_time:
            # Period spans midnight
            return current_time >= period.start_time or current_time <= period.end_time
        else:
            # Normal period (doesn't span midnight)
            return period.start_time <= current_time <= period.end_time

    def _risk_score_to_level(self, score: int) -> RiskLevel:
        """Convert risk score to risk level category.

        Args:
            score: Risk score (0-100)

        Returns:
            RiskLevel enum value
        """
        if score >= 80:
            return RiskLevel.CRITICAL
        elif score >= 60:
            return RiskLevel.HIGH
        elif score >= 40:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
