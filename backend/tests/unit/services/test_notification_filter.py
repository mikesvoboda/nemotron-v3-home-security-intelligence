"""Unit tests for NotificationFilterService.

Tests cover:
- should_notify() method with various scenarios
- is_quiet_period() method for quiet hours checking
- Global preferences filtering (enabled, risk filters)
- Per-camera settings filtering (enabled, risk threshold)
- Quiet hours period checking
- Day of week logic
"""

from datetime import datetime, time

import pytest

from backend.models.notification_preferences import (
    CameraNotificationSetting,
    DayOfWeek,
    NotificationPreferences,
    QuietHoursPeriod,
    RiskLevel,
)
from backend.services.notification_filter import NotificationFilterService

# Mark as unit tests
pytestmark = pytest.mark.unit


class TestNotificationFilterService:
    """Tests for NotificationFilterService."""

    def test_should_notify_when_disabled_globally(self):
        """Test that notifications are blocked when globally disabled."""
        prefs = NotificationPreferences(enabled=False)
        service = NotificationFilterService()

        result = service.should_notify(
            risk_score=80,
            camera_id="test_camera",
            timestamp=datetime(2025, 1, 7, 12, 0),
            global_prefs=prefs,
        )

        assert result is False

    def test_should_notify_when_risk_not_in_filters(self):
        """Test that notifications are blocked when risk level not in filters."""
        prefs = NotificationPreferences(
            enabled=True,
            risk_filters=[RiskLevel.CRITICAL.value, RiskLevel.HIGH.value],
        )
        service = NotificationFilterService()

        # Low risk (0-39) not in filters
        result = service.should_notify(
            risk_score=30,
            camera_id="test_camera",
            timestamp=datetime(2025, 1, 7, 12, 0),
            global_prefs=prefs,
        )

        assert result is False

    def test_should_notify_when_risk_in_filters(self):
        """Test that notifications pass when risk level is in filters."""
        prefs = NotificationPreferences(
            enabled=True,
            risk_filters=[RiskLevel.CRITICAL.value, RiskLevel.HIGH.value],
        )
        service = NotificationFilterService()

        # High risk (60-79) in filters
        result = service.should_notify(
            risk_score=70,
            camera_id="test_camera",
            timestamp=datetime(2025, 1, 7, 12, 0),
            global_prefs=prefs,
        )

        assert result is True

    def test_should_notify_with_camera_disabled(self):
        """Test that notifications are blocked for disabled cameras."""
        prefs = NotificationPreferences(enabled=True, risk_filters=[RiskLevel.HIGH.value])
        camera_setting = CameraNotificationSetting(
            camera_id="test_camera",
            enabled=False,
            risk_threshold=0,
        )
        service = NotificationFilterService()

        result = service.should_notify(
            risk_score=70,
            camera_id="test_camera",
            timestamp=datetime(2025, 1, 7, 12, 0),
            global_prefs=prefs,
            camera_setting=camera_setting,
        )

        assert result is False

    def test_should_notify_below_camera_threshold(self):
        """Test that notifications are blocked when below camera threshold."""
        prefs = NotificationPreferences(enabled=True, risk_filters=[RiskLevel.HIGH.value])
        camera_setting = CameraNotificationSetting(
            camera_id="test_camera",
            enabled=True,
            risk_threshold=75,
        )
        service = NotificationFilterService()

        # Risk 70 is below threshold of 75
        result = service.should_notify(
            risk_score=70,
            camera_id="test_camera",
            timestamp=datetime(2025, 1, 7, 12, 0),
            global_prefs=prefs,
            camera_setting=camera_setting,
        )

        assert result is False

    def test_should_notify_above_camera_threshold(self):
        """Test that notifications pass when above camera threshold."""
        prefs = NotificationPreferences(enabled=True, risk_filters=[RiskLevel.HIGH.value])
        camera_setting = CameraNotificationSetting(
            camera_id="test_camera",
            enabled=True,
            risk_threshold=65,
        )
        service = NotificationFilterService()

        # Risk 70 is above threshold of 65
        result = service.should_notify(
            risk_score=70,
            camera_id="test_camera",
            timestamp=datetime(2025, 1, 7, 12, 0),
            global_prefs=prefs,
            camera_setting=camera_setting,
        )

        assert result is True

    def test_should_notify_during_quiet_hours(self):
        """Test that notifications are blocked during quiet hours."""
        prefs = NotificationPreferences(enabled=True, risk_filters=[RiskLevel.HIGH.value])
        quiet_period = QuietHoursPeriod(
            label="Night",
            start_time=time(22, 0),
            end_time=time(6, 0),
            days=[day.value for day in DayOfWeek],  # All days
        )
        service = NotificationFilterService()

        # Tuesday at 23:00 (during quiet hours)
        result = service.should_notify(
            risk_score=70,
            camera_id="test_camera",
            timestamp=datetime(2025, 1, 7, 23, 0),  # Tuesday
            global_prefs=prefs,
            quiet_periods=[quiet_period],
        )

        assert result is False

    def test_should_notify_outside_quiet_hours(self):
        """Test that notifications pass outside quiet hours."""
        prefs = NotificationPreferences(enabled=True, risk_filters=[RiskLevel.HIGH.value])
        quiet_period = QuietHoursPeriod(
            label="Night",
            start_time=time(22, 0),
            end_time=time(6, 0),
            days=[day.value for day in DayOfWeek],
        )
        service = NotificationFilterService()

        # Tuesday at 12:00 (outside quiet hours)
        result = service.should_notify(
            risk_score=70,
            camera_id="test_camera",
            timestamp=datetime(2025, 1, 7, 12, 0),  # Tuesday
            global_prefs=prefs,
            quiet_periods=[quiet_period],
        )

        assert result is True

    def test_should_notify_quiet_hours_wrong_day(self):
        """Test that notifications pass when quiet period doesn't apply to day."""
        prefs = NotificationPreferences(enabled=True, risk_filters=[RiskLevel.HIGH.value])
        quiet_period = QuietHoursPeriod(
            label="Weekday Nights",
            start_time=time(22, 0),
            end_time=time(6, 0),
            days=["monday", "tuesday", "wednesday", "thursday", "friday"],
        )
        service = NotificationFilterService()

        # Saturday at 23:00 (quiet period only for weekdays)
        result = service.should_notify(
            risk_score=70,
            camera_id="test_camera",
            timestamp=datetime(2025, 1, 11, 23, 0),  # Saturday
            global_prefs=prefs,
            quiet_periods=[quiet_period],
        )

        assert result is True

    def test_is_quiet_period_active(self):
        """Test is_quiet_period returns True during quiet hours."""
        period = QuietHoursPeriod(
            label="Night",
            start_time=time(22, 0),
            end_time=time(6, 0),
            days=[day.value for day in DayOfWeek],
        )
        service = NotificationFilterService()

        # Tuesday at 23:00
        result = service.is_quiet_period(datetime(2025, 1, 7, 23, 0), period)
        assert result is True

    def test_is_quiet_period_inactive(self):
        """Test is_quiet_period returns False outside quiet hours."""
        period = QuietHoursPeriod(
            label="Night",
            start_time=time(22, 0),
            end_time=time(6, 0),
            days=[day.value for day in DayOfWeek],
        )
        service = NotificationFilterService()

        # Tuesday at 12:00
        result = service.is_quiet_period(datetime(2025, 1, 7, 12, 0), period)
        assert result is False

    def test_risk_score_to_level_critical(self):
        """Test risk score to level conversion for critical (80-100)."""
        service = NotificationFilterService()
        assert service._risk_score_to_level(80) == RiskLevel.CRITICAL
        assert service._risk_score_to_level(90) == RiskLevel.CRITICAL
        assert service._risk_score_to_level(100) == RiskLevel.CRITICAL

    def test_risk_score_to_level_high(self):
        """Test risk score to level conversion for high (60-79)."""
        service = NotificationFilterService()
        assert service._risk_score_to_level(60) == RiskLevel.HIGH
        assert service._risk_score_to_level(70) == RiskLevel.HIGH
        assert service._risk_score_to_level(79) == RiskLevel.HIGH

    def test_risk_score_to_level_medium(self):
        """Test risk score to level conversion for medium (40-59)."""
        service = NotificationFilterService()
        assert service._risk_score_to_level(40) == RiskLevel.MEDIUM
        assert service._risk_score_to_level(50) == RiskLevel.MEDIUM
        assert service._risk_score_to_level(59) == RiskLevel.MEDIUM

    def test_risk_score_to_level_low(self):
        """Test risk score to level conversion for low (0-39)."""
        service = NotificationFilterService()
        assert service._risk_score_to_level(0) == RiskLevel.LOW
        assert service._risk_score_to_level(20) == RiskLevel.LOW
        assert service._risk_score_to_level(39) == RiskLevel.LOW

    def test_multiple_quiet_periods(self):
        """Test notification filtering with multiple quiet periods."""
        prefs = NotificationPreferences(enabled=True, risk_filters=[RiskLevel.HIGH.value])
        period1 = QuietHoursPeriod(
            label="Morning",
            start_time=time(0, 0),
            end_time=time(8, 0),
            days=[day.value for day in DayOfWeek],
        )
        period2 = QuietHoursPeriod(
            label="Night",
            start_time=time(22, 0),
            end_time=time(23, 59),
            days=[day.value for day in DayOfWeek],
        )
        service = NotificationFilterService()

        # During first period (7:00)
        result = service.should_notify(
            risk_score=70,
            camera_id="test_camera",
            timestamp=datetime(2025, 1, 7, 7, 0),
            global_prefs=prefs,
            quiet_periods=[period1, period2],
        )
        assert result is False

        # During second period (22:30)
        result = service.should_notify(
            risk_score=70,
            camera_id="test_camera",
            timestamp=datetime(2025, 1, 7, 22, 30),
            global_prefs=prefs,
            quiet_periods=[period1, period2],
        )
        assert result is False

        # Outside both periods (12:00)
        result = service.should_notify(
            risk_score=70,
            camera_id="test_camera",
            timestamp=datetime(2025, 1, 7, 12, 0),
            global_prefs=prefs,
            quiet_periods=[period1, period2],
        )
        assert result is True

    def test_all_conditions_pass(self):
        """Test notification passes when all conditions are met."""
        prefs = NotificationPreferences(
            enabled=True,
            risk_filters=[RiskLevel.CRITICAL.value, RiskLevel.HIGH.value],
        )
        camera_setting = CameraNotificationSetting(
            camera_id="test_camera",
            enabled=True,
            risk_threshold=50,
        )
        service = NotificationFilterService()

        # All conditions pass: enabled, risk 70 in filters, above threshold, not quiet hours
        result = service.should_notify(
            risk_score=70,
            camera_id="test_camera",
            timestamp=datetime(2025, 1, 7, 12, 0),
            global_prefs=prefs,
            camera_setting=camera_setting,
            quiet_periods=[],
        )

        assert result is True
