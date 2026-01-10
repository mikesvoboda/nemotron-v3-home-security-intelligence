"""Tests for notification preferences API endpoints.

This module tests the notification preferences endpoints for:
- Global notification preferences (GET, PUT)
- Camera-specific notification settings (GET, PUT)
- Quiet hours periods (GET, POST, DELETE)

All tests use mocked database operations following TDD methodology.
"""

from datetime import time
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import SQLAlchemyError

from backend.core import get_db
from backend.main import app
from backend.models.notification_preferences import (
    CameraNotificationSetting,
    DayOfWeek,
    NotificationPreferences,
    NotificationSound,
    QuietHoursPeriod,
    RiskLevel,
)


@pytest.fixture
def mock_db() -> AsyncMock:
    """Create a mock database session."""
    mock = AsyncMock()
    mock.execute = AsyncMock()
    mock.commit = AsyncMock()
    mock.refresh = AsyncMock()
    mock.add = MagicMock()
    mock.delete = AsyncMock()
    mock.rollback = AsyncMock()
    return mock


def create_mock_db_dependency(mock_db: AsyncMock):
    """Create a mock dependency that yields mock database."""

    async def _mock_db_dependency():
        yield mock_db

    return _mock_db_dependency


# =============================================================================
# Global Preferences Tests
# =============================================================================


class TestGetNotificationPreferences:
    """Tests for GET /api/notification-preferences endpoint."""

    @pytest.mark.asyncio
    async def test_get_preferences_returns_existing(self, mock_db: AsyncMock) -> None:
        """Test getting existing notification preferences."""
        # Mock database query returning existing preferences
        mock_prefs = MagicMock(spec=NotificationPreferences)
        mock_prefs.id = 1
        mock_prefs.enabled = True
        mock_prefs.sound = NotificationSound.DEFAULT.value
        mock_prefs.risk_filters = [
            RiskLevel.CRITICAL.value,
            RiskLevel.HIGH.value,
            RiskLevel.MEDIUM.value,
        ]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_prefs
        mock_db.execute.return_value = mock_result

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/notification-preferences/")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == 1
            assert data["enabled"] is True
            assert data["sound"] == "default"
            assert data["risk_filters"] == ["critical", "high", "medium"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_preferences_creates_default_if_missing(self, mock_db: AsyncMock) -> None:
        """Test creating default preferences when none exist."""
        # Mock database query returning None (no preferences)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Mock the refresh to set attributes on the created object
        async def mock_refresh(obj):
            obj.id = 1
            obj.enabled = True
            obj.sound = NotificationSound.DEFAULT.value
            obj.risk_filters = [
                RiskLevel.CRITICAL.value,
                RiskLevel.HIGH.value,
                RiskLevel.MEDIUM.value,
            ]

        mock_db.refresh.side_effect = mock_refresh

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/notification-preferences/")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == 1
            assert data["enabled"] is True
            assert data["sound"] == "default"
            assert "critical" in data["risk_filters"]
            assert "high" in data["risk_filters"]
            assert "medium" in data["risk_filters"]

            # Verify preferences were created and saved
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
        finally:
            app.dependency_overrides.clear()


class TestUpdateNotificationPreferences:
    """Tests for PUT /api/notification-preferences endpoint."""

    @pytest.mark.asyncio
    async def test_update_preferences_all_fields(self, mock_db: AsyncMock) -> None:
        """Test updating all preference fields."""
        # Mock existing preferences
        mock_prefs = MagicMock(spec=NotificationPreferences)
        mock_prefs.id = 1
        mock_prefs.enabled = False
        mock_prefs.sound = NotificationSound.ALERT.value
        mock_prefs.risk_filters = [RiskLevel.CRITICAL.value]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_prefs
        mock_db.execute.return_value = mock_result

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.put(
                    "/api/notification-preferences/",
                    json={
                        "enabled": False,
                        "sound": "alert",
                        "risk_filters": ["critical"],
                    },
                )

            assert response.status_code == 200
            data = response.json()
            assert data["enabled"] is False
            assert data["sound"] == "alert"
            assert data["risk_filters"] == ["critical"]

            # Verify database operations
            mock_db.commit.assert_called_once()
            mock_db.refresh.assert_called_once()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_preferences_partial_fields(self, mock_db: AsyncMock) -> None:
        """Test updating only some preference fields."""
        # Mock existing preferences
        mock_prefs = MagicMock(spec=NotificationPreferences)
        mock_prefs.id = 1
        mock_prefs.enabled = True
        mock_prefs.sound = NotificationSound.DEFAULT.value
        mock_prefs.risk_filters = [RiskLevel.CRITICAL.value, RiskLevel.HIGH.value]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_prefs
        mock_db.execute.return_value = mock_result

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.put(
                    "/api/notification-preferences/",
                    json={"enabled": False},  # Only update enabled
                )

            assert response.status_code == 200
            assert mock_prefs.enabled is False
            # Other fields should not be changed
            assert mock_prefs.sound == NotificationSound.DEFAULT.value
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_preferences_creates_if_missing(self, mock_db: AsyncMock) -> None:
        """Test creating preferences when updating if they don't exist."""
        # Mock database query returning None (no preferences)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Create a real NotificationPreferences object for modification
        created_prefs = NotificationPreferences(id=1)

        # Mock add to capture the object
        def mock_add(obj):
            # Copy attributes to our created_prefs
            created_prefs.enabled = obj.enabled if hasattr(obj, "enabled") else True
            created_prefs.sound = (
                obj.sound if hasattr(obj, "sound") else NotificationSound.DEFAULT.value
            )
            created_prefs.risk_filters = obj.risk_filters if hasattr(obj, "risk_filters") else []

        mock_db.add.side_effect = mock_add

        # Mock refresh to return our object
        async def mock_refresh(obj):
            obj.id = 1
            obj.enabled = True
            obj.sound = NotificationSound.URGENT.value
            obj.risk_filters = [RiskLevel.CRITICAL.value]

        mock_db.refresh.side_effect = mock_refresh

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.put(
                    "/api/notification-preferences/",
                    json={"sound": "urgent", "risk_filters": ["critical"]},
                )

            assert response.status_code == 200
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_preferences_invalid_sound(self, mock_db: AsyncMock) -> None:
        """Test error handling for invalid sound value."""
        # Mock existing preferences
        mock_prefs = MagicMock(spec=NotificationPreferences)
        mock_prefs.id = 1

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_prefs
        mock_db.execute.return_value = mock_result

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.put(
                    "/api/notification-preferences/",
                    json={"sound": "invalid_sound"},
                )

            assert response.status_code == 400
            assert "Invalid sound value" in response.json()["detail"]
            # Database should not be committed
            mock_db.commit.assert_not_called()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_preferences_invalid_risk_level(self, mock_db: AsyncMock) -> None:
        """Test error handling for invalid risk level."""
        # Mock existing preferences
        mock_prefs = MagicMock(spec=NotificationPreferences)
        mock_prefs.id = 1

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_prefs
        mock_db.execute.return_value = mock_result

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.put(
                    "/api/notification-preferences/",
                    json={"risk_filters": ["critical", "invalid_level"]},
                )

            assert response.status_code == 400
            assert "Invalid risk level" in response.json()["detail"]
            mock_db.commit.assert_not_called()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_preferences_valid_sound_values(self, mock_db: AsyncMock) -> None:
        """Test all valid sound values are accepted."""
        mock_prefs = MagicMock(spec=NotificationPreferences)
        mock_prefs.id = 1

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_prefs
        mock_db.execute.return_value = mock_result

        valid_sounds = ["none", "default", "alert", "chime", "urgent"]

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            for sound in valid_sounds:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.put(
                        "/api/notification-preferences/",
                        json={"sound": sound},
                    )

                assert response.status_code == 200, f"Failed for sound: {sound}"
                assert mock_prefs.sound == sound
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_preferences_valid_risk_levels(self, mock_db: AsyncMock) -> None:
        """Test all valid risk levels are accepted."""
        valid_levels = [
            ["critical"],
            ["high"],
            ["medium"],
            ["low"],
            ["critical", "high", "medium", "low"],
        ]

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            for levels in valid_levels:
                # Create fresh mock for each iteration
                mock_prefs = MagicMock(spec=NotificationPreferences)
                mock_prefs.id = 1
                mock_prefs.enabled = True
                mock_prefs.sound = NotificationSound.DEFAULT.value
                mock_prefs.risk_filters = []  # Will be updated

                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = mock_prefs
                mock_db.execute.return_value = mock_result

                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.put(
                        "/api/notification-preferences/",
                        json={"risk_filters": levels},
                    )

                assert response.status_code == 200, f"Failed for levels: {levels}"
                assert mock_prefs.risk_filters == levels
        finally:
            app.dependency_overrides.clear()


# =============================================================================
# Camera Settings Tests
# =============================================================================


class TestGetAllCameraSettings:
    """Tests for GET /api/notification-preferences/cameras endpoint."""

    @pytest.mark.asyncio
    async def test_get_all_camera_settings_empty(self, mock_db: AsyncMock) -> None:
        """Test getting camera settings when none exist."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/notification-preferences/cameras")

            assert response.status_code == 200
            data = response.json()
            assert data["items"] == []
            assert data["pagination"]["total"] == 0
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_all_camera_settings_multiple(self, mock_db: AsyncMock) -> None:
        """Test getting multiple camera settings."""
        # Mock camera settings
        setting1 = MagicMock(spec=CameraNotificationSetting)
        setting1.id = str(uuid4())
        setting1.camera_id = "front_door"
        setting1.enabled = True
        setting1.risk_threshold = 50

        setting2 = MagicMock(spec=CameraNotificationSetting)
        setting2.id = str(uuid4())
        setting2.camera_id = "back_yard"
        setting2.enabled = False
        setting2.risk_threshold = 70

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [setting1, setting2]
        mock_db.execute.return_value = mock_result

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/notification-preferences/cameras")

            assert response.status_code == 200
            data = response.json()
            assert data["pagination"]["total"] == 2
            assert len(data["items"]) == 2
            assert data["items"][0]["camera_id"] == "front_door"
            assert data["items"][1]["camera_id"] == "back_yard"
        finally:
            app.dependency_overrides.clear()


class TestGetCameraSetting:
    """Tests for GET /api/notification-preferences/cameras/{camera_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_camera_setting_found(self, mock_db: AsyncMock) -> None:
        """Test getting specific camera setting."""
        mock_setting = MagicMock(spec=CameraNotificationSetting)
        mock_setting.id = str(uuid4())
        mock_setting.camera_id = "front_door"
        mock_setting.enabled = True
        mock_setting.risk_threshold = 60

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_setting
        mock_db.execute.return_value = mock_result

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/notification-preferences/cameras/front_door")

            assert response.status_code == 200
            data = response.json()
            assert data["camera_id"] == "front_door"
            assert data["enabled"] is True
            assert data["risk_threshold"] == 60
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_camera_setting_not_found(self, mock_db: AsyncMock) -> None:
        """Test 404 when camera setting not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/notification-preferences/cameras/nonexistent")

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()


class TestUpdateCameraSetting:
    """Tests for PUT /api/notification-preferences/cameras/{camera_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_camera_setting_existing(self, mock_db: AsyncMock) -> None:
        """Test updating existing camera setting."""
        # Mock camera exists
        from backend.models import Camera

        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"

        # Mock existing setting
        mock_setting = MagicMock(spec=CameraNotificationSetting)
        mock_setting.id = str(uuid4())
        mock_setting.camera_id = "front_door"
        mock_setting.enabled = True
        mock_setting.risk_threshold = 50

        # Setup two execute calls: first for camera check, second for setting
        camera_result = MagicMock()
        camera_result.scalar_one_or_none.return_value = mock_camera

        setting_result = MagicMock()
        setting_result.scalar_one_or_none.return_value = mock_setting

        mock_db.execute.side_effect = [camera_result, setting_result]

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.put(
                    "/api/notification-preferences/cameras/front_door",
                    json={"enabled": False, "risk_threshold": 75},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["camera_id"] == "front_door"
            assert mock_setting.enabled is False
            assert mock_setting.risk_threshold == 75

            mock_db.commit.assert_called_once()
            mock_db.refresh.assert_called_once()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_camera_setting_create_new(self, mock_db: AsyncMock) -> None:
        """Test creating camera setting if it doesn't exist."""
        # Mock camera exists
        from backend.models import Camera

        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"

        camera_result = MagicMock()
        camera_result.scalar_one_or_none.return_value = mock_camera

        # No existing setting
        setting_result = MagicMock()
        setting_result.scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = [camera_result, setting_result]

        # Mock refresh to set ID
        async def mock_refresh(obj):
            obj.id = str(uuid4())

        mock_db.refresh.side_effect = mock_refresh

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.put(
                    "/api/notification-preferences/cameras/front_door",
                    json={"enabled": True, "risk_threshold": 80},
                )

            assert response.status_code == 200
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_camera_setting_camera_not_found(self, mock_db: AsyncMock) -> None:
        """Test 404 when camera doesn't exist."""
        camera_result = MagicMock()
        camera_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = camera_result

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.put(
                    "/api/notification-preferences/cameras/nonexistent",
                    json={"enabled": True},
                )

            assert response.status_code == 404
            assert "Camera" in response.json()["detail"]
            assert "not found" in response.json()["detail"]
            mock_db.commit.assert_not_called()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_camera_setting_partial_update(self, mock_db: AsyncMock) -> None:
        """Test updating only some fields of camera setting."""
        # Mock camera exists
        from backend.models import Camera

        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"

        # Mock existing setting
        mock_setting = MagicMock(spec=CameraNotificationSetting)
        mock_setting.id = str(uuid4())
        mock_setting.camera_id = "front_door"
        mock_setting.enabled = True
        mock_setting.risk_threshold = 50

        camera_result = MagicMock()
        camera_result.scalar_one_or_none.return_value = mock_camera

        setting_result = MagicMock()
        setting_result.scalar_one_or_none.return_value = mock_setting

        mock_db.execute.side_effect = [camera_result, setting_result]

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.put(
                    "/api/notification-preferences/cameras/front_door",
                    json={"risk_threshold": 90},  # Only update threshold
                )

            assert response.status_code == 200
            # Enabled should remain unchanged
            assert mock_setting.enabled is True
            # Threshold should be updated
            assert mock_setting.risk_threshold == 90
        finally:
            app.dependency_overrides.clear()


# =============================================================================
# Quiet Hours Tests
# =============================================================================


class TestGetQuietHours:
    """Tests for GET /api/notification-preferences/quiet-hours endpoint."""

    @pytest.mark.asyncio
    async def test_get_quiet_hours_empty(self, mock_db: AsyncMock) -> None:
        """Test getting quiet hours when none exist."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/notification-preferences/quiet-hours")

            assert response.status_code == 200
            data = response.json()
            assert data["items"] == []
            assert data["pagination"]["total"] == 0
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_quiet_hours_multiple(self, mock_db: AsyncMock) -> None:
        """Test getting multiple quiet hours periods."""
        period1 = MagicMock(spec=QuietHoursPeriod)
        period1.id = str(uuid4())
        period1.label = "Night Time"
        period1.start_time = time(22, 0, 0)
        period1.end_time = time(6, 0, 0)
        period1.days = [DayOfWeek.MONDAY.value, DayOfWeek.TUESDAY.value]

        period2 = MagicMock(spec=QuietHoursPeriod)
        period2.id = str(uuid4())
        period2.label = "Afternoon Nap"
        period2.start_time = time(14, 0, 0)
        period2.end_time = time(16, 0, 0)
        period2.days = [DayOfWeek.SATURDAY.value, DayOfWeek.SUNDAY.value]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [period1, period2]
        mock_db.execute.return_value = mock_result

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/notification-preferences/quiet-hours")

            assert response.status_code == 200
            data = response.json()
            assert data["pagination"]["total"] == 2
            assert len(data["items"]) == 2
            assert data["items"][0]["label"] == "Night Time"
            assert data["items"][1]["label"] == "Afternoon Nap"
        finally:
            app.dependency_overrides.clear()


class TestCreateQuietHoursPeriod:
    """Tests for POST /api/notification-preferences/quiet-hours endpoint."""

    @pytest.mark.asyncio
    async def test_create_quiet_hours_period_success(self, mock_db: AsyncMock) -> None:
        """Test creating a quiet hours period successfully."""

        # Mock refresh to set ID
        async def mock_refresh(obj):
            obj.id = str(uuid4())

        mock_db.refresh.side_effect = mock_refresh

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/notification-preferences/quiet-hours",
                    json={
                        "label": "Afternoon Quiet",
                        "start_time": "14:00:00",
                        "end_time": "16:00:00",  # Must be > start_time
                        "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
                    },
                )

            assert response.status_code == 201
            data = response.json()
            assert "id" in data
            assert data["label"] == "Afternoon Quiet"
            assert data["start_time"] == "14:00:00"
            assert data["end_time"] == "16:00:00"
            assert len(data["days"]) == 5

            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_quiet_hours_period_invalid_time_range(self, mock_db: AsyncMock) -> None:
        """Test error when start_time >= end_time."""
        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/notification-preferences/quiet-hours",
                    json={
                        "label": "Invalid Period",
                        "start_time": "22:00:00",
                        "end_time": "22:00:00",  # Equal to start_time
                        "days": ["monday"],
                    },
                )

            assert response.status_code == 400
            assert "start_time must not equal end_time" in response.json()["detail"]
            mock_db.add.assert_not_called()
            mock_db.commit.assert_not_called()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_quiet_hours_period_start_after_end(self, mock_db: AsyncMock) -> None:
        """Test overnight period (start_time > end_time) is allowed."""
        # Mock refresh to set ID
        async def mock_refresh(obj: Any) -> None:
            if not hasattr(obj, "id") or obj.id is None:
                obj.id = str(uuid4())

        mock_db.refresh.side_effect = mock_refresh

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/notification-preferences/quiet-hours",
                    json={
                        "label": "Overnight Period",
                        "start_time": "22:00:00",
                        "end_time": "06:00:00",  # Earlier in clock time (overnight period)
                        "days": ["monday"],
                    },
                )

            # Overnight periods are now supported (wraps to next day)
            assert response.status_code == 201
            data = response.json()
            assert data["label"] == "Overnight Period"
            assert data["start_time"] == "22:00:00"
            assert data["end_time"] == "06:00:00"
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_quiet_hours_period_database_error(self, mock_db: AsyncMock) -> None:
        """Test error handling when database commit fails."""
        mock_db.commit.side_effect = SQLAlchemyError("Database error")

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/notification-preferences/quiet-hours",
                    json={
                        "label": "Night Time",
                        "start_time": "22:00:00",
                        "end_time": "23:00:00",
                        "days": ["monday"],
                    },
                )

            assert response.status_code == 500
            assert "Failed to create quiet hours period" in response.json()["detail"]
            mock_db.rollback.assert_called_once()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_quiet_hours_period_default_days(self, mock_db: AsyncMock) -> None:
        """Test creating quiet hours period with default days (all week)."""

        # Mock refresh to set ID
        async def mock_refresh(obj):
            obj.id = str(uuid4())
            # Set default days if not specified
            if not obj.days:
                obj.days = [day.value for day in DayOfWeek]

        mock_db.refresh.side_effect = mock_refresh

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/notification-preferences/quiet-hours",
                    json={
                        "label": "All Week",
                        "start_time": "22:00:00",
                        "end_time": "23:00:00",
                        # days not specified
                    },
                )

            assert response.status_code == 201
            data = response.json()
            # Should have all 7 days
            assert len(data["days"]) == 7
        finally:
            app.dependency_overrides.clear()


class TestDeleteQuietHoursPeriod:
    """Tests for DELETE /api/notification-preferences/quiet-hours/{period_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_quiet_hours_period_success(self, mock_db: AsyncMock) -> None:
        """Test deleting a quiet hours period successfully."""
        period_id = str(uuid4())
        mock_period = MagicMock(spec=QuietHoursPeriod)
        mock_period.id = period_id

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_period
        mock_db.execute.return_value = mock_result

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.delete(
                    f"/api/notification-preferences/quiet-hours/{period_id}"
                )

            assert response.status_code == 204
            mock_db.delete.assert_called_once_with(mock_period)
            mock_db.commit.assert_called_once()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_delete_quiet_hours_period_not_found(self, mock_db: AsyncMock) -> None:
        """Test 404 when quiet hours period not found."""
        period_id = str(uuid4())

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.delete(
                    f"/api/notification-preferences/quiet-hours/{period_id}"
                )

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
            mock_db.delete.assert_not_called()
            mock_db.commit.assert_not_called()
        finally:
            app.dependency_overrides.clear()
