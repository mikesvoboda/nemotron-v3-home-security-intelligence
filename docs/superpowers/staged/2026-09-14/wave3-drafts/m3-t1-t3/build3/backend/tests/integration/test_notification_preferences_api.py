"""Integration tests for notification preferences API endpoints.

Tests the /api/notification-preferences routes including:
- GET /api/notification-preferences/ - Get global preferences
- PUT /api/notification-preferences/ - Update global preferences
- GET /api/notification-preferences/cameras - Get all camera settings
- GET /api/notification-preferences/cameras/{camera_id} - Get camera setting
- PUT /api/notification-preferences/cameras/{camera_id} - Update camera setting
- GET /api/notification-preferences/quiet-hours - Get quiet hours
- POST /api/notification-preferences/quiet-hours - Add quiet period
- DELETE /api/notification-preferences/quiet-hours/{period_id} - Delete period

Uses shared fixtures from conftest.py:
- integration_db: Clean database with initialized schema
- client: httpx AsyncClient with test app
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient

    from backend.models.camera import Camera


@pytest.fixture
async def async_client(client: AsyncClient) -> AsyncClient:
    """Alias for shared client fixture for backward compatibility."""
    return client


@pytest.fixture
async def sample_camera(integration_db: str) -> Camera:
    """Create a sample camera for notification preference tests."""
    from backend.core.database import get_session
    from backend.models.camera import Camera

    async with get_session() as db:
        camera = Camera(
            id="test_camera",
            name="Test Camera",
            folder_path="/export/foscam/test",
            status="online",
        )
        db.add(camera)
        await db.commit()
        await db.refresh(camera)
        return camera


# =============================================================================
# Global Preferences Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_global_preferences_default(async_client: AsyncClient, integration_db: str):
    """Test getting default global notification preferences."""
    response = await async_client.get("/api/notification-preferences/")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == 1
    assert data["enabled"] is True
    assert data["sound"] == "default"
    assert "critical" in data["risk_filters"]
    assert "high" in data["risk_filters"]
    assert "medium" in data["risk_filters"]


@pytest.mark.asyncio
async def test_update_global_preferences(async_client: AsyncClient, integration_db: str):
    """Test updating global notification preferences."""
    # Update preferences
    update_data = {
        "enabled": False,
        "sound": "alert",
        "risk_filters": ["critical"],
    }
    response = await async_client.put("/api/notification-preferences/", json=update_data)
    assert response.status_code == 200

    data = response.json()
    assert data["enabled"] is False
    assert data["sound"] == "alert"
    assert data["risk_filters"] == ["critical"]

    # Verify persistence
    response = await async_client.get("/api/notification-preferences/")
    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is False
    assert data["sound"] == "alert"


@pytest.mark.asyncio
async def test_update_global_preferences_partial(async_client: AsyncClient, integration_db: str):
    """Test partial update of global preferences."""
    # Update only enabled field
    update_data = {"enabled": False}
    response = await async_client.put("/api/notification-preferences/", json=update_data)
    assert response.status_code == 200

    data = response.json()
    assert data["enabled"] is False
    assert data["sound"] == "default"  # Unchanged


@pytest.mark.asyncio
async def test_update_global_preferences_invalid_sound(
    async_client: AsyncClient, integration_db: str
):
    """Test updating preferences with invalid sound value."""
    update_data = {"sound": "invalid_sound"}
    response = await async_client.put("/api/notification-preferences/", json=update_data)
    assert response.status_code == 400


# =============================================================================
# Camera Settings Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_camera_settings_empty(async_client: AsyncClient, integration_db: str):
    """Test getting camera settings when none exist."""
    response = await async_client.get("/api/notification-preferences/cameras")
    assert response.status_code == 200

    data = response.json()
    assert data["items"] == []
    assert data["pagination"]["total"] == 0


@pytest.mark.asyncio
async def test_create_and_get_camera_setting(
    async_client: AsyncClient, integration_db: str, sample_camera: Camera
):
    """Test creating and retrieving a camera notification setting."""
    # Create setting
    setting_data = {
        "enabled": False,
        "risk_threshold": 75,
    }
    response = await async_client.put(
        f"/api/notification-preferences/cameras/{sample_camera.id}",
        json=setting_data,
    )
    assert response.status_code == 200

    data = response.json()
    assert data["camera_id"] == sample_camera.id
    assert data["enabled"] is False
    assert data["risk_threshold"] == 75

    # Get all settings
    response = await async_client.get("/api/notification-preferences/cameras")
    assert response.status_code == 200
    data = response.json()
    assert data["pagination"]["total"] == 1
    assert data["items"][0]["camera_id"] == sample_camera.id


@pytest.mark.asyncio
async def test_get_camera_setting_by_id(
    async_client: AsyncClient, integration_db: str, sample_camera: Camera
):
    """Test getting a specific camera setting by camera ID."""
    # Create setting
    setting_data = {"enabled": True, "risk_threshold": 50}
    response = await async_client.put(
        f"/api/notification-preferences/cameras/{sample_camera.id}",
        json=setting_data,
    )
    assert response.status_code == 200

    # Get specific setting
    response = await async_client.get(f"/api/notification-preferences/cameras/{sample_camera.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["camera_id"] == sample_camera.id
    assert data["enabled"] is True
    assert data["risk_threshold"] == 50


@pytest.mark.asyncio
async def test_get_camera_setting_not_found(async_client: AsyncClient, integration_db: str):
    """Test getting setting for non-existent camera."""
    response = await async_client.get("/api/notification-preferences/cameras/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_camera_setting(
    async_client: AsyncClient, integration_db: str, sample_camera: Camera
):
    """Test updating an existing camera setting."""
    # Create initial setting
    setting_data = {"enabled": True, "risk_threshold": 30}
    response = await async_client.put(
        f"/api/notification-preferences/cameras/{sample_camera.id}",
        json=setting_data,
    )
    assert response.status_code == 200

    # Update setting
    update_data = {"risk_threshold": 80}
    response = await async_client.put(
        f"/api/notification-preferences/cameras/{sample_camera.id}",
        json=update_data,
    )
    assert response.status_code == 200

    data = response.json()
    assert data["enabled"] is True  # Unchanged
    assert data["risk_threshold"] == 80  # Updated


@pytest.mark.asyncio
async def test_update_camera_setting_invalid_threshold(
    async_client: AsyncClient, integration_db: str, sample_camera: Camera
):
    """Test updating camera setting with invalid threshold."""
    # Test threshold > 100
    response = await async_client.put(
        f"/api/notification-preferences/cameras/{sample_camera.id}",
        json={"risk_threshold": 150},
    )
    assert response.status_code == 422  # Validation error

    # Test threshold < 0
    response = await async_client.put(
        f"/api/notification-preferences/cameras/{sample_camera.id}",
        json={"risk_threshold": -10},
    )
    assert response.status_code == 422


# =============================================================================
# Quiet Hours Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_quiet_hours_empty(async_client: AsyncClient, integration_db: str):
    """Test getting quiet hours when none exist."""
    response = await async_client.get("/api/notification-preferences/quiet-hours")
    assert response.status_code == 200

    data = response.json()
    assert data["items"] == []
    assert data["pagination"]["total"] == 0


@pytest.mark.asyncio
async def test_create_quiet_hours_period(async_client: AsyncClient, integration_db: str):
    """Test creating a quiet hours period."""
    period_data = {
        "label": "Night Time",
        "start_time": "22:00:00",
        "end_time": "06:00:00",
        "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
    }
    response = await async_client.post(
        "/api/notification-preferences/quiet-hours", json=period_data
    )
    assert response.status_code == 201

    data = response.json()
    assert data["label"] == "Night Time"
    assert data["start_time"] == "22:00:00"
    assert data["end_time"] == "06:00:00"
    assert len(data["days"]) == 5
    assert "id" in data


@pytest.mark.asyncio
async def test_create_quiet_hours_with_all_days(async_client: AsyncClient, integration_db: str):
    """Test creating a quiet period with all days (default)."""
    period_data = {
        "label": "Every Night",
        "start_time": "23:00:00",
        "end_time": "07:00:00",
    }
    response = await async_client.post(
        "/api/notification-preferences/quiet-hours", json=period_data
    )
    assert response.status_code == 201

    data = response.json()
    assert len(data["days"]) == 7  # All days by default


@pytest.mark.asyncio
async def test_get_quiet_hours_after_creation(async_client: AsyncClient, integration_db: str):
    """Test getting quiet hours after creating periods."""
    # Create two periods
    period1 = {
        "label": "Night",
        "start_time": "22:00:00",
        "end_time": "06:00:00",
        "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
    }
    period2 = {
        "label": "Weekend Morning",
        "start_time": "00:00:00",
        "end_time": "10:00:00",
        "days": ["saturday", "sunday"],
    }

    await async_client.post("/api/notification-preferences/quiet-hours", json=period1)
    await async_client.post("/api/notification-preferences/quiet-hours", json=period2)

    # Get all periods
    response = await async_client.get("/api/notification-preferences/quiet-hours")
    assert response.status_code == 200

    data = response.json()
    assert data["pagination"]["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_delete_quiet_hours_period(async_client: AsyncClient, integration_db: str):
    """Test deleting a quiet hours period."""
    # Create period
    period_data = {
        "label": "Test Period",
        "start_time": "20:00:00",
        "end_time": "08:00:00",
    }
    response = await async_client.post(
        "/api/notification-preferences/quiet-hours", json=period_data
    )
    assert response.status_code == 201
    period_id = response.json()["id"]

    # Delete period
    response = await async_client.delete(f"/api/notification-preferences/quiet-hours/{period_id}")
    assert response.status_code == 204

    # Verify deletion
    response = await async_client.get("/api/notification-preferences/quiet-hours")
    data = response.json()
    assert data["pagination"]["total"] == 0


@pytest.mark.asyncio
async def test_delete_quiet_hours_period_not_found(async_client: AsyncClient, integration_db: str):
    """Test deleting a non-existent quiet hours period."""
    fake_uuid = "550e8400-e29b-41d4-a716-446655440000"
    response = await async_client.delete(f"/api/notification-preferences/quiet-hours/{fake_uuid}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_quiet_hours_invalid_time_range(
    async_client: AsyncClient, integration_db: str
):
    """Test creating quiet period with invalid time range (start == end).

    Note: Overnight periods (start > end) are valid (e.g., 22:00 to 06:00).
    """
    period_data = {
        "label": "Invalid",
        "start_time": "10:00:00",
        "end_time": "10:00:00",  # Same as start - invalid
    }
    response = await async_client.post(
        "/api/notification-preferences/quiet-hours", json=period_data
    )
    # Should fail validation (zero-length period)
    assert response.status_code in [400, 422, 500]
