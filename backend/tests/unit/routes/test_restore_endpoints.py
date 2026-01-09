"""Unit tests for restore endpoints for soft-deleted records.

Tests cover:
- POST /api/events/{event_id}/restore - Restore a soft-deleted event
- GET /api/events/deleted - List all deleted events
- POST /api/cameras/{camera_id}/restore - Restore a soft-deleted camera
- GET /api/cameras/deleted - List all deleted cameras

NEM-1955: Add restore API endpoints for soft-deleted records
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.dependencies import get_cache_service_dep
from backend.api.routes.cameras import router as cameras_router
from backend.api.routes.events import router as events_router
from backend.core.database import get_db
from backend.models.camera import Camera
from backend.models.event import Event
from backend.tests.factories import CameraFactory, EventFactory

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock database session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    return session


@pytest.fixture
def mock_cache_service() -> MagicMock:
    """Create a mock cache service that returns None for all cache operations."""
    mock_cache = MagicMock()
    mock_cache.get = AsyncMock(return_value=None)
    mock_cache.set = AsyncMock(return_value=True)
    mock_cache.invalidate_pattern = AsyncMock(return_value=0)
    mock_cache.invalidate_events = AsyncMock(return_value=0)
    mock_cache.invalidate_cameras = AsyncMock(return_value=0)
    mock_cache.invalidate_event_stats = AsyncMock(return_value=0)
    return mock_cache


@pytest.fixture
def events_client(mock_db_session: AsyncMock, mock_cache_service: MagicMock) -> TestClient:
    """Create a test client for events endpoints with mocked dependencies."""
    app = FastAPI()
    app.include_router(events_router)

    async def override_get_db() -> Any:
        yield mock_db_session

    async def override_cache_service() -> Any:
        yield mock_cache_service

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_cache_service_dep] = override_cache_service

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def cameras_client(mock_db_session: AsyncMock, mock_cache_service: MagicMock) -> TestClient:
    """Create a test client for cameras endpoints with mocked dependencies."""
    app = FastAPI()
    app.include_router(cameras_router)

    async def override_get_db() -> Any:
        yield mock_db_session

    async def override_cache_service() -> Any:
        yield mock_cache_service

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_cache_service_dep] = override_cache_service

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def deleted_event() -> Event:
    """Create a soft-deleted event for testing."""
    return EventFactory(
        id=1,
        camera_id="front_door",
        deleted_at=datetime.now(UTC) - timedelta(hours=1),
    )


@pytest.fixture
def active_event() -> Event:
    """Create an active (non-deleted) event for testing."""
    return EventFactory(
        id=2,
        camera_id="front_door",
        deleted_at=None,
    )


@pytest.fixture
def deleted_camera() -> Camera:
    """Create a soft-deleted camera for testing."""
    return CameraFactory(
        id="deleted_camera",
        name="Deleted Camera",
        deleted_at=datetime.now(UTC) - timedelta(hours=1),
    )


@pytest.fixture
def active_camera() -> Camera:
    """Create an active (non-deleted) camera for testing."""
    return CameraFactory(
        id="active_camera",
        name="Active Camera",
        deleted_at=None,
    )


# =============================================================================
# Event Restore Endpoint Tests (POST /api/events/{event_id}/restore)
# =============================================================================


class TestRestoreEvent:
    """Tests for POST /api/events/{event_id}/restore endpoint."""

    def test_restore_deleted_event_success(
        self,
        events_client: TestClient,
        mock_db_session: AsyncMock,
        deleted_event: Event,
    ) -> None:
        """Test successfully restoring a soft-deleted event."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = deleted_event
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = events_client.post("/api/events/1/restore")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        # After restore, deleted_at should be None
        assert deleted_event.deleted_at is None

    def test_restore_event_not_found(
        self,
        events_client: TestClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test restoring a non-existent event returns 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = events_client.post("/api/events/999/restore")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_restore_non_deleted_event_returns_409(
        self,
        events_client: TestClient,
        mock_db_session: AsyncMock,
        active_event: Event,
    ) -> None:
        """Test restoring a non-deleted event returns 409 Conflict."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = active_event
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = events_client.post("/api/events/2/restore")

        assert response.status_code == 409
        assert "not deleted" in response.json()["detail"].lower()


# =============================================================================
# List Deleted Events Tests (GET /api/events/deleted)
# =============================================================================


class TestListDeletedEvents:
    """Tests for GET /api/events/deleted endpoint."""

    def test_list_deleted_events_empty(
        self,
        events_client: TestClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test listing deleted events when none exist."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = events_client.get("/api/events/deleted")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["pagination"]["total"] == 0

    def test_list_deleted_events_with_data(
        self,
        events_client: TestClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test listing deleted events with existing data."""
        deleted_events = [
            EventFactory(id=1, deleted_at=datetime.now(UTC) - timedelta(hours=1)),
            EventFactory(id=2, deleted_at=datetime.now(UTC) - timedelta(hours=2)),
            EventFactory(id=3, deleted_at=datetime.now(UTC) - timedelta(hours=3)),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = deleted_events
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = events_client.get("/api/events/deleted")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        assert data["pagination"]["total"] == 3

    def test_list_deleted_events_ordered_by_deleted_at_desc(
        self,
        events_client: TestClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test that deleted events are ordered by deleted_at descending."""
        # Create events deleted at different times
        now = datetime.now(UTC)
        deleted_events = [
            EventFactory(id=1, deleted_at=now - timedelta(hours=3)),  # oldest
            EventFactory(id=2, deleted_at=now - timedelta(hours=1)),  # newest
            EventFactory(id=3, deleted_at=now - timedelta(hours=2)),  # middle
        ]
        # Mock should return in descending order
        ordered_events = sorted(
            deleted_events,
            key=lambda e: e.deleted_at,
            reverse=True,  # type: ignore[arg-type]
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = ordered_events
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = events_client.get("/api/events/deleted")

        assert response.status_code == 200
        data = response.json()
        # Most recently deleted should be first
        assert data["items"][0]["id"] == 2
        assert data["items"][1]["id"] == 3
        assert data["items"][2]["id"] == 1


# =============================================================================
# Camera Restore Endpoint Tests (POST /api/cameras/{camera_id}/restore)
# =============================================================================


class TestRestoreCamera:
    """Tests for POST /api/cameras/{camera_id}/restore endpoint."""

    def test_restore_deleted_camera_success(
        self,
        cameras_client: TestClient,
        mock_db_session: AsyncMock,
        deleted_camera: Camera,
    ) -> None:
        """Test successfully restoring a soft-deleted camera."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = deleted_camera
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = cameras_client.post("/api/cameras/deleted_camera/restore")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "deleted_camera"
        # After restore, deleted_at should be None
        assert deleted_camera.deleted_at is None

    def test_restore_camera_not_found(
        self,
        cameras_client: TestClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test restoring a non-existent camera returns 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = cameras_client.post("/api/cameras/nonexistent/restore")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_restore_non_deleted_camera_returns_400(
        self,
        cameras_client: TestClient,
        mock_db_session: AsyncMock,
        active_camera: Camera,
    ) -> None:
        """Test restoring a non-deleted camera returns 400 Bad Request."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = active_camera
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = cameras_client.post("/api/cameras/active_camera/restore")

        assert response.status_code == 400
        assert "not deleted" in response.json()["detail"].lower()


# =============================================================================
# List Deleted Cameras Tests (GET /api/cameras/deleted)
# =============================================================================


class TestListDeletedCameras:
    """Tests for GET /api/cameras/deleted endpoint."""

    def test_list_deleted_cameras_empty(
        self,
        cameras_client: TestClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test listing deleted cameras when none exist."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = cameras_client.get("/api/cameras/deleted")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["pagination"]["total"] == 0

    def test_list_deleted_cameras_with_data(
        self,
        cameras_client: TestClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test listing deleted cameras with existing data."""
        deleted_cameras = [
            CameraFactory(id="cam1", deleted_at=datetime.now(UTC) - timedelta(hours=1)),
            CameraFactory(id="cam2", deleted_at=datetime.now(UTC) - timedelta(hours=2)),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = deleted_cameras
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = cameras_client.get("/api/cameras/deleted")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["pagination"]["total"] == 2

    def test_list_deleted_cameras_ordered_by_deleted_at_desc(
        self,
        cameras_client: TestClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test that deleted cameras are ordered by deleted_at descending."""
        now = datetime.now(UTC)
        deleted_cameras = [
            CameraFactory(id="cam1", deleted_at=now - timedelta(hours=3)),  # oldest
            CameraFactory(id="cam2", deleted_at=now - timedelta(hours=1)),  # newest
            CameraFactory(id="cam3", deleted_at=now - timedelta(hours=2)),  # middle
        ]
        # Mock should return in descending order
        ordered_cameras = sorted(
            deleted_cameras,
            key=lambda c: c.deleted_at,
            reverse=True,  # type: ignore[arg-type]
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = ordered_cameras
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = cameras_client.get("/api/cameras/deleted")

        assert response.status_code == 200
        data = response.json()
        # Most recently deleted should be first
        assert data["items"][0]["id"] == "cam2"
        assert data["items"][1]["id"] == "cam3"
        assert data["items"][2]["id"] == "cam1"
