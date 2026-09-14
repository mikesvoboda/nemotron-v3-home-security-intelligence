# Integration Tests for Backend Models

## Purpose

This directory contains integration tests for SQLAlchemy ORM models that require a real database connection. These tests validate database constraints, relationships, cascade behaviors, and unique constraints that cannot be tested with mocks.

## Key Files

| File                               | Tests For                                                            | Test Count |
| ---------------------------------- | -------------------------------------------------------------------- | ---------- |
| `test_notification_preferences.py` | NotificationPreferences, CameraNotificationSetting, QuietHoursPeriod | ~5         |

## Test Markers

All tests in this directory are marked as integration tests:

```python
pytestmark = pytest.mark.integration
```

## Test Patterns

### Singleton Constraint Tests

Tests verify database-level singleton enforcement:

```python
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
```

### Unique Constraint Tests

Tests verify unique constraint enforcement:

```python
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
```

### Cascade Delete Tests

Tests verify foreign key cascade delete behavior:

```python
@pytest.mark.asyncio
async def test_camera_notification_setting_cascade_delete(session):
    """Test that notification setting is deleted when camera is deleted.

    This validates the CASCADE delete behavior of the foreign key relationship.
    """
    from sqlalchemy import delete
    from backend.models import Camera

    # Create camera and notification setting
    camera = Camera(id="test_camera", name="Test Camera", ...)
    setting = CameraNotificationSetting(camera_id="test_camera", enabled=True)
    session.add_all([camera, setting])
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
```

### Time Range Validation Tests

Tests verify model behavior with special time ranges:

```python
@pytest.mark.asyncio
async def test_quiet_hours_period_allows_midnight_spanning(session):
    """Test that quiet hours periods can span midnight.

    According to the model documentation, periods can span midnight
    (e.g., 22:00 to 06:00) where start_time > end_time indicates
    a period that wraps to the next day.
    """
    # Create period that spans midnight (valid case)
    period = QuietHoursPeriod(
        label="Night Sleep",
        start_time=time(22, 0),  # 10 PM
        end_time=time(6, 0),     # 6 AM next day
    )
    session.add(period)
    await session.commit()

    # Verify period was created successfully
    result = await session.execute(
        select(QuietHoursPeriod).where(QuietHoursPeriod.label == "Night Sleep")
    )
    saved_period = result.scalar_one()
    assert saved_period.start_time > saved_period.end_time  # Midnight spanning
```

## Fixtures Used

| Fixture   | Source                      | Purpose                                         |
| --------- | --------------------------- | ----------------------------------------------- |
| `session` | `backend/tests/conftest.py` | Async database session with savepoint isolation |

## Running Tests

```bash
# Run all models integration tests
uv run pytest backend/tests/integration/models/ -v -n0

# Run specific test file
uv run pytest backend/tests/integration/models/test_notification_preferences.py -v -n0

# Run with verbose output
uv run pytest backend/tests/integration/models/ -v -n0 --capture=no
```

## Test Requirements

- **Database**: Requires PostgreSQL database connection (via `DATABASE_URL`)
- **Tables**: Tests assume all model tables exist (created by Alembic migrations)
- **Isolation**: Uses savepoint-based transaction isolation for test cleanup
- **Foreign Keys**: Related tables must exist (e.g., `cameras` for `CameraNotificationSetting`)

## What These Tests Validate

1. **Primary Key Constraints**: Singleton patterns via unique id=1
2. **Unique Constraints**: One-to-one relationships enforced at database level
3. **Foreign Key Constraints**: Referential integrity between related models
4. **Cascade Behaviors**: DELETE CASCADE properly propagates to child tables
5. **Data Type Handling**: Time ranges, enums, and other special types
6. **Edge Cases**: Midnight-spanning time ranges, boundary conditions

## Related Documentation

| Path                                          | Purpose                      |
| --------------------------------------------- | ---------------------------- |
| `/backend/models/AGENTS.md`                   | Models module documentation  |
| `/backend/models/notification_preferences.py` | Model implementation         |
| `/backend/tests/AGENTS.md`                    | Test infrastructure overview |
