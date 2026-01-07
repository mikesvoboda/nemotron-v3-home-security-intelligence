"""Unit tests for NotificationPreferences models.

Tests cover:
- NotificationPreferences model (global settings)
- CameraNotificationSetting model (per-camera settings)
- QuietHoursPeriod model (quiet hours configuration)
- Model initialization and default values
- Field validation and constraints
- String representation (__repr__)
- Enum values
"""

from datetime import time

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy.exc import IntegrityError

from backend.models.notification_preferences import (
    CameraNotificationSetting,
    DayOfWeek,
    NotificationPreferences,
    NotificationSound,
    QuietHoursPeriod,
    RiskLevel,
)

# Mark as unit tests
pytestmark = pytest.mark.unit


# =============================================================================
# RiskLevel Enum Tests
# =============================================================================


class TestRiskLevel:
    """Tests for RiskLevel enum."""

    def test_risk_level_values(self):
        """Test that risk level enum has expected values."""
        assert RiskLevel.CRITICAL.value == "critical"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.LOW.value == "low"

    def test_risk_level_membership(self):
        """Test risk level enum membership."""
        assert "critical" in [level.value for level in RiskLevel]
        assert "high" in [level.value for level in RiskLevel]
        assert "medium" in [level.value for level in RiskLevel]
        assert "low" in [level.value for level in RiskLevel]


# =============================================================================
# NotificationSound Enum Tests
# =============================================================================


class TestNotificationSound:
    """Tests for NotificationSound enum."""

    def test_notification_sound_values(self):
        """Test that notification sound enum has expected values."""
        assert NotificationSound.NONE.value == "none"
        assert NotificationSound.DEFAULT.value == "default"
        assert NotificationSound.ALERT.value == "alert"
        assert NotificationSound.CHIME.value == "chime"
        assert NotificationSound.URGENT.value == "urgent"


# =============================================================================
# DayOfWeek Enum Tests
# =============================================================================


class TestDayOfWeek:
    """Tests for DayOfWeek enum."""

    def test_day_of_week_values(self):
        """Test that day of week enum has all 7 days."""
        days = [day.value for day in DayOfWeek]
        assert len(days) == 7
        assert "monday" in days
        assert "tuesday" in days
        assert "wednesday" in days
        assert "thursday" in days
        assert "friday" in days
        assert "saturday" in days
        assert "sunday" in days


# =============================================================================
# NotificationPreferences Model Tests
# =============================================================================


class TestNotificationPreferences:
    """Tests for NotificationPreferences model."""

    def test_default_values(self):
        """Test that model initializes with correct default values."""
        prefs = NotificationPreferences()
        assert prefs.id == 1
        assert prefs.enabled is True
        assert prefs.sound == NotificationSound.DEFAULT.value
        assert RiskLevel.CRITICAL.value in prefs.risk_filters
        assert RiskLevel.HIGH.value in prefs.risk_filters
        assert RiskLevel.MEDIUM.value in prefs.risk_filters
        assert RiskLevel.LOW.value not in prefs.risk_filters

    def test_custom_values(self):
        """Test creating model with custom values."""
        prefs = NotificationPreferences(
            enabled=False,
            sound=NotificationSound.ALERT.value,
            risk_filters=[RiskLevel.CRITICAL.value],
        )
        assert prefs.enabled is False
        assert prefs.sound == NotificationSound.ALERT.value
        assert prefs.risk_filters == [RiskLevel.CRITICAL.value]

    def test_repr(self):
        """Test string representation."""
        prefs = NotificationPreferences(
            enabled=True,
            sound=NotificationSound.DEFAULT.value,
            risk_filters=[RiskLevel.CRITICAL.value],
        )
        repr_str = repr(prefs)
        assert "NotificationPreferences" in repr_str
        assert "enabled=True" in repr_str
        assert "sound='default'" in repr_str
        assert "risk_filters=['critical']" in repr_str

    def test_singleton_id(self):
        """Test that ID is always 1 (singleton pattern)."""
        prefs1 = NotificationPreferences()
        prefs2 = NotificationPreferences()
        assert prefs1.id == 1
        assert prefs2.id == 1


# =============================================================================
# CameraNotificationSetting Model Tests
# =============================================================================


class TestCameraNotificationSetting:
    """Tests for CameraNotificationSetting model."""

    def test_default_values(self):
        """Test that model initializes with correct default values."""
        setting = CameraNotificationSetting(camera_id="front_door")
        assert setting.camera_id == "front_door"
        assert setting.enabled is True
        assert setting.risk_threshold == 0
        assert setting.id is not None  # UUID generated

    def test_custom_values(self):
        """Test creating model with custom values."""
        setting = CameraNotificationSetting(
            camera_id="back_yard",
            enabled=False,
            risk_threshold=50,
        )
        assert setting.camera_id == "back_yard"
        assert setting.enabled is False
        assert setting.risk_threshold == 50

    def test_repr(self):
        """Test string representation."""
        setting = CameraNotificationSetting(
            camera_id="front_door",
            enabled=True,
            risk_threshold=30,
        )
        repr_str = repr(setting)
        assert "CameraNotificationSetting" in repr_str
        assert "camera_id='front_door'" in repr_str
        assert "enabled=True" in repr_str
        assert "risk_threshold=30" in repr_str

    @given(st.integers(min_value=0, max_value=100))
    @settings(max_examples=20)
    def test_valid_risk_threshold_range(self, threshold):
        """Test that risk threshold accepts valid range 0-100."""
        setting = CameraNotificationSetting(
            camera_id="test_camera",
            risk_threshold=threshold,
        )
        assert setting.risk_threshold == threshold

    def test_uuid_generation(self):
        """Test that each instance gets a unique UUID."""
        setting1 = CameraNotificationSetting(camera_id="camera1")
        setting2 = CameraNotificationSetting(camera_id="camera2")
        assert setting1.id != setting2.id
        assert isinstance(setting1.id, str)
        assert len(setting1.id) == 36  # UUID format


# =============================================================================
# QuietHoursPeriod Model Tests
# =============================================================================


class TestQuietHoursPeriod:
    """Tests for QuietHoursPeriod model."""

    def test_default_values(self):
        """Test that model initializes with correct default values."""
        period = QuietHoursPeriod(
            label="Night",
            start_time=time(22, 0),
            end_time=time(6, 0),
        )
        assert period.label == "Night"
        assert period.start_time == time(22, 0)
        assert period.end_time == time(6, 0)
        assert len(period.days) == 7  # All days by default
        assert "monday" in period.days
        assert "sunday" in period.days

    def test_custom_days(self):
        """Test creating period with specific days."""
        period = QuietHoursPeriod(
            label="Weekday Nights",
            start_time=time(23, 0),
            end_time=time(7, 0),
            days=["monday", "tuesday", "wednesday", "thursday", "friday"],
        )
        assert len(period.days) == 5
        assert "monday" in period.days
        assert "saturday" not in period.days
        assert "sunday" not in period.days

    def test_repr(self):
        """Test string representation."""
        period = QuietHoursPeriod(
            label="Sleep",
            start_time=time(22, 0),
            end_time=time(6, 0),
            days=["monday", "tuesday"],
        )
        repr_str = repr(period)
        assert "QuietHoursPeriod" in repr_str
        assert "label='Sleep'" in repr_str
        assert "start_time=22:00:00" in repr_str
        assert "end_time=06:00:00" in repr_str
        assert "days=['monday', 'tuesday']" in repr_str

    def test_uuid_generation(self):
        """Test that each instance gets a unique UUID."""
        period1 = QuietHoursPeriod(
            label="Period1",
            start_time=time(22, 0),
            end_time=time(6, 0),
        )
        period2 = QuietHoursPeriod(
            label="Period2",
            start_time=time(23, 0),
            end_time=time(7, 0),
        )
        assert period1.id != period2.id
        assert isinstance(period1.id, str)
        assert len(period1.id) == 36  # UUID format

    def test_weekend_only_period(self):
        """Test creating a weekend-only quiet period."""
        period = QuietHoursPeriod(
            label="Weekend",
            start_time=time(0, 0),
            end_time=time(10, 0),
            days=["saturday", "sunday"],
        )
        assert len(period.days) == 2
        assert "saturday" in period.days
        assert "sunday" in period.days
        assert "monday" not in period.days


# =============================================================================
# Integration Tests (Database Constraints)
# Note: These tests require database fixtures and should be run as integration tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.skip(reason="Integration test - requires isolated_db fixture from integration tests")
@pytest.mark.asyncio
async def test_notification_preferences_singleton_constraint(isolated_db):
    """Test that only one NotificationPreferences row can exist with id=1.

    This is an integration test that requires database access.
    """
    from sqlalchemy import select

    async with isolated_db() as session:
        # Create first preferences
        prefs1 = NotificationPreferences(id=1, enabled=True)
        session.add(prefs1)
        await session.commit()

        # Try to create second preferences with same id
        prefs2 = NotificationPreferences(id=1, enabled=False)
        session.add(prefs2)

        with pytest.raises(IntegrityError):
            await session.commit()

        await session.rollback()

        # Verify only one row exists
        result = await session.execute(select(NotificationPreferences))
        all_prefs = result.scalars().all()
        assert len(all_prefs) == 1


@pytest.mark.integration
@pytest.mark.skip(reason="Integration test - requires isolated_db fixture from integration tests")
@pytest.mark.asyncio
async def test_camera_notification_setting_unique_camera(isolated_db):
    """Test that each camera can only have one notification setting.

    This is an integration test that requires database access.
    """
    from backend.models import Camera

    async with isolated_db() as session:
        # Create camera
        camera = Camera(
            id="test_camera",
            name="Test Camera",
            folder_path="/export/test",
            status="online",
        )
        session.add(camera)
        await session.commit()

        # Create first setting
        setting1 = CameraNotificationSetting(camera_id="test_camera", enabled=True)
        session.add(setting1)
        await session.commit()

        # Try to create second setting for same camera
        setting2 = CameraNotificationSetting(camera_id="test_camera", enabled=False)
        session.add(setting2)

        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.integration
@pytest.mark.skip(reason="Integration test - requires isolated_db fixture from integration tests")
@pytest.mark.asyncio
async def test_camera_notification_setting_cascade_delete(isolated_db):
    """Test that notification setting is deleted when camera is deleted.

    This is an integration test that requires database access.
    """
    from sqlalchemy import select

    from backend.models import Camera

    async with isolated_db() as session:
        # Create camera
        camera = Camera(
            id="test_camera",
            name="Test Camera",
            folder_path="/export/test",
            status="online",
        )
        session.add(camera)
        await session.commit()

        # Create notification setting
        setting = CameraNotificationSetting(camera_id="test_camera", enabled=True)
        session.add(setting)
        await session.commit()

        # Delete camera
        await session.delete(camera)
        await session.commit()

        # Verify setting was cascade deleted
        result = await session.execute(
            select(CameraNotificationSetting).where(
                CameraNotificationSetting.camera_id == "test_camera"
            )
        )
        assert result.scalar_one_or_none() is None


@pytest.mark.integration
@pytest.mark.skip(reason="Integration test - requires isolated_db fixture from integration tests")
@pytest.mark.asyncio
async def test_quiet_hours_time_range_constraint(isolated_db):
    """Test that start_time must be less than end_time.

    This is an integration test that requires database access.
    """
    async with isolated_db() as session:
        # Create period with invalid time range (start > end)
        period = QuietHoursPeriod(
            label="Invalid",
            start_time=time(10, 0),
            end_time=time(8, 0),  # Earlier than start
        )
        session.add(period)

        with pytest.raises(IntegrityError):
            await session.commit()
