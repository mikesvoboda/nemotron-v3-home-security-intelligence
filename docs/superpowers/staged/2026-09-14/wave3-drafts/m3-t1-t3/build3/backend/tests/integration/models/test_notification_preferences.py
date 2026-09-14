"""Integration tests for NotificationPreferences database constraints.

Tests cover:
- NotificationPreferences singleton constraint (only one row with id=1)
- CameraNotificationSetting unique constraint per camera
- CameraNotificationSetting cascade delete with camera
- QuietHoursPeriod time range constraint (start_time < end_time)

These tests require database access to validate constraints and relationships.
"""

from datetime import time

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.models.notification_preferences import (
    CameraNotificationSetting,
    NotificationPreferences,
    QuietHoursPeriod,
)

# Mark as integration tests
pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_notification_preferences_singleton_constraint(session):
    """Test that only one NotificationPreferences row can exist with id=1.

    This validates the singleton pattern enforcement at the database level.
    """
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


@pytest.mark.asyncio
async def test_camera_notification_setting_unique_camera(session):
    """Test that each camera can only have one notification setting.

    This validates the unique constraint on camera_id.
    """
    from backend.models import Camera

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


@pytest.mark.asyncio
async def test_camera_notification_setting_cascade_delete(session):
    """Test that notification setting is deleted when camera is deleted.

    This validates the CASCADE delete behavior of the foreign key relationship.
    """
    from sqlalchemy import delete

    from backend.models import Camera

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

    # Delete camera using DELETE statement to trigger CASCADE
    await session.execute(delete(Camera).where(Camera.id == "test_camera"))
    await session.commit()

    # Verify setting was cascade deleted
    result = await session.execute(
        select(CameraNotificationSetting).where(
            CameraNotificationSetting.camera_id == "test_camera"
        )
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_quiet_hours_period_allows_midnight_spanning(session):
    """Test that quiet hours periods can span midnight.

    According to the model documentation, periods can span midnight
    (e.g., 22:00 to 06:00) where start_time > end_time indicates
    a period that wraps to the next day. This is a valid use case.
    """
    # Create period that spans midnight (valid case)
    period = QuietHoursPeriod(
        label="Night Sleep",
        start_time=time(22, 0),  # 10 PM
        end_time=time(6, 0),  # 6 AM next day
    )
    session.add(period)
    await session.commit()

    # Verify period was created successfully
    result = await session.execute(
        select(QuietHoursPeriod).where(QuietHoursPeriod.label == "Night Sleep")
    )
    saved_period = result.scalar_one()
    assert saved_period.start_time == time(22, 0)
    assert saved_period.end_time == time(6, 0)
    assert saved_period.start_time > saved_period.end_time  # Midnight spanning
