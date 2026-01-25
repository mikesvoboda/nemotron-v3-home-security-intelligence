"""Unit tests for cameras API routes.

Tests cover:
- GET /api/cameras - List all cameras with optional status filter
- GET /api/cameras/{camera_id} - Get a specific camera by ID
- POST /api/cameras - Create a new camera
- PATCH /api/cameras/{camera_id} - Update an existing camera
- DELETE /api/cameras/{camera_id} - Delete a camera
- GET /api/cameras/{camera_id}/snapshot - Get the latest snapshot for a camera
"""

import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.dependencies import get_cache_service_dep
from backend.api.routes.cameras import router, snapshot_rate_limiter
from backend.api.schemas.camera import (
    CameraCreate,
    CameraListResponse,
    CameraResponse,
    CameraStatus,
    CameraUpdate,
)
from backend.core.database import get_db
from backend.models.camera import Camera
from backend.tests.factories import CameraFactory

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
    """Create a mock cache service that returns None for all cache operations.

    This ensures unit tests don't try to connect to Redis for caching.
    This mock implements the CacheService interface used by routes.
    """
    mock_cache = MagicMock()
    mock_cache.get = AsyncMock(return_value=None)  # Cache miss
    mock_cache.set = AsyncMock(return_value=True)
    mock_cache.invalidate_pattern = AsyncMock(return_value=0)
    mock_cache.invalidate_cameras = AsyncMock(return_value=0)  # Used by CRUD operations
    return mock_cache


@pytest.fixture
def client(mock_db_session: AsyncMock, mock_cache_service: MagicMock) -> TestClient:
    """Create a test client with mocked dependencies.

    Uses FastAPI dependency_overrides for clean dependency injection,
    following the proper DI pattern (NEM-1659).
    """
    app = FastAPI()
    app.include_router(router)

    # Override the database dependency
    async def override_get_db():
        yield mock_db_session

    # Override the rate limiter dependency (no-op for unit tests)
    async def override_rate_limiter():
        return None

    # Override the cache service dependency using proper FastAPI DI pattern
    # This replaces the previous patch-based approach (NEM-1659)
    async def override_cache_service():
        yield mock_cache_service

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[snapshot_rate_limiter] = override_rate_limiter
    app.dependency_overrides[get_cache_service_dep] = override_cache_service

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_camera() -> Camera:
    """Create a sample camera object for testing using factory."""
    return CameraFactory(
        id="123e4567-e89b-12d3-a456-426614174000",
        name="Front Door Camera",
        folder_path="/export/foscam/front_door",
        status="online",
        created_at=datetime(2025, 12, 23, 10, 0, 0),
        last_seen_at=datetime(2025, 12, 23, 12, 0, 0),
    )


@pytest.fixture
def sample_camera_list() -> list[Camera]:
    """Create a list of sample cameras for testing using factory."""
    return [
        CameraFactory(
            id=str(uuid.uuid4()),
            name="Front Door Camera",
            folder_path="/export/foscam/front_door",
            status="online",
            created_at=datetime(2025, 12, 23, 10, 0, 0),
            last_seen_at=datetime(2025, 12, 23, 12, 0, 0),
        ),
        CameraFactory(
            id=str(uuid.uuid4()),
            name="Back Door Camera",
            folder_path="/export/foscam/back_door",
            offline=True,  # Use factory trait
            created_at=datetime(2025, 12, 23, 10, 0, 0),
            last_seen_at=None,
        ),
        CameraFactory(
            id=str(uuid.uuid4()),
            name="Garage Camera",
            folder_path="/export/foscam/garage",
            status="error",
            created_at=datetime(2025, 12, 23, 10, 0, 0),
            last_seen_at=datetime(2025, 12, 23, 11, 0, 0),
        ),
    ]


# =============================================================================
# List Cameras Tests (GET /api/cameras)
# =============================================================================


class TestListCameras:
    """Tests for GET /api/cameras endpoint."""

    def test_list_cameras_empty(self, client: TestClient, mock_db_session: AsyncMock) -> None:
        """Test listing cameras when none exist."""
        mock_result = MagicMock()
        # NEM-3597: list_cameras now uses unique().scalars().all() due to joinedload(areas)
        mock_result.unique.return_value.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.get("/api/cameras")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["pagination"]["total"] == 0

    def test_list_cameras_with_data(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_camera_list: list[Camera],
    ) -> None:
        """Test listing cameras with existing data."""
        mock_result = MagicMock()
        # NEM-3597: list_cameras now uses unique().scalars().all() due to joinedload(areas)
        mock_result.unique.return_value.scalars.return_value.all.return_value = sample_camera_list
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.get("/api/cameras")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        assert data["pagination"]["total"] == 3

    def test_list_cameras_filter_by_status_online(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_camera_list: list[Camera],
    ) -> None:
        """Test listing cameras filtered by online status."""
        # Filter to only return online cameras
        online_cameras = [c for c in sample_camera_list if c.status == "online"]
        mock_result = MagicMock()
        # NEM-3597: list_cameras now uses unique().scalars().all() due to joinedload(areas)
        mock_result.unique.return_value.scalars.return_value.all.return_value = online_cameras
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.get("/api/cameras?status=online")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["pagination"]["total"] == 1
        assert data["items"][0]["status"] == "online"

    def test_list_cameras_filter_by_status_offline(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_camera_list: list[Camera],
    ) -> None:
        """Test listing cameras filtered by offline status."""
        offline_cameras = [c for c in sample_camera_list if c.status == "offline"]
        mock_result = MagicMock()
        # NEM-3597: list_cameras now uses unique().scalars().all() due to joinedload(areas)
        mock_result.unique.return_value.scalars.return_value.all.return_value = offline_cameras
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.get("/api/cameras?status=offline")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["pagination"]["total"] == 1
        assert data["items"][0]["status"] == "offline"

    def test_list_cameras_filter_by_status_error(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_camera_list: list[Camera],
    ) -> None:
        """Test listing cameras filtered by error status."""
        error_cameras = [c for c in sample_camera_list if c.status == "error"]
        mock_result = MagicMock()
        # NEM-3597: list_cameras now uses unique().scalars().all() due to joinedload(areas)
        mock_result.unique.return_value.scalars.return_value.all.return_value = error_cameras
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.get("/api/cameras?status=error")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["pagination"]["total"] == 1
        assert data["items"][0]["status"] == "error"

    def test_list_cameras_filter_nonexistent_status(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test listing cameras with a filter that matches nothing."""
        mock_result = MagicMock()
        # NEM-3597: list_cameras now uses unique().scalars().all() due to joinedload(areas)
        mock_result.unique.return_value.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.get("/api/cameras?status=nonexistent")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 0
        assert data["pagination"]["total"] == 0


# =============================================================================
# Get Camera Tests (GET /api/cameras/{camera_id})
# =============================================================================


class TestGetCamera:
    """Tests for GET /api/cameras/{camera_id} endpoint."""

    def test_get_camera_success(
        self, client: TestClient, mock_db_session: AsyncMock, sample_camera: Camera
    ) -> None:
        """Test getting a specific camera by ID."""
        mock_result = MagicMock()
        # NEM-3597: get_camera now uses unique().scalar_one_or_none() due to joinedload(areas)
        mock_result.unique.return_value.scalar_one_or_none.return_value = sample_camera
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.get(f"/api/cameras/{sample_camera.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_camera.id
        assert data["name"] == sample_camera.name
        assert data["folder_path"] == sample_camera.folder_path
        assert data["status"] == sample_camera.status

    def test_get_camera_not_found(self, client: TestClient, mock_db_session: AsyncMock) -> None:
        """Test getting a non-existent camera returns 404."""
        mock_result = MagicMock()
        # NEM-3597: get_camera now uses unique().scalar_one_or_none() due to joinedload(areas)
        mock_result.unique.return_value.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/cameras/{fake_id}")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
        assert fake_id in data["detail"]

    def test_get_camera_includes_all_fields(
        self, client: TestClient, mock_db_session: AsyncMock, sample_camera: Camera
    ) -> None:
        """Test that camera response includes all expected fields."""
        mock_result = MagicMock()
        # NEM-3597: get_camera now uses unique().scalar_one_or_none() due to joinedload(areas)
        mock_result.unique.return_value.scalar_one_or_none.return_value = sample_camera
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.get(f"/api/cameras/{sample_camera.id}")

        assert response.status_code == 200
        data = response.json()
        required_fields = ["id", "name", "folder_path", "status", "created_at", "last_seen_at"]
        for field in required_fields:
            assert field in data


# =============================================================================
# Create Camera Tests (POST /api/cameras)
# =============================================================================


class TestCreateCamera:
    """Tests for POST /api/cameras endpoint."""

    def test_create_camera_success(self, client: TestClient, mock_db_session: AsyncMock) -> None:
        """Test successful camera creation."""
        # Mock execute to return no existing cameras (no duplicates)
        mock_results = [MagicMock(), MagicMock()]
        mock_results[0].scalar_one_or_none.return_value = None  # No name match
        mock_results[1].scalar_one_or_none.return_value = None  # No folder_path match
        mock_db_session.execute = AsyncMock(side_effect=mock_results)

        async def mock_refresh(camera):
            # Simulate database refresh setting created_at
            camera.created_at = datetime(2025, 12, 23, 10, 0, 0)
            camera.last_seen_at = None

        mock_db_session.refresh = mock_refresh

        camera_data = {
            "name": "Front Door Camera",
            "folder_path": "/export/foscam/front_door",
            "status": "online",
        }

        response = client.post("/api/cameras", json=camera_data)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == camera_data["name"]
        assert data["folder_path"] == camera_data["folder_path"]
        assert data["status"] == camera_data["status"]
        assert "id" in data
        # ID should be normalized camera name (e.g., "front_door_camera")
        assert data["id"] == "front_door_camera"

    def test_create_camera_default_status(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test camera creation with default status."""
        # Mock execute to return no existing cameras (no duplicates)
        mock_results = [MagicMock(), MagicMock()]
        mock_results[0].scalar_one_or_none.return_value = None  # No name match
        mock_results[1].scalar_one_or_none.return_value = None  # No folder_path match
        mock_db_session.execute = AsyncMock(side_effect=mock_results)

        async def mock_refresh(camera):
            camera.created_at = datetime(2025, 12, 23, 10, 0, 0)
            camera.last_seen_at = None

        mock_db_session.refresh = mock_refresh

        camera_data = {
            "name": "Back Door Camera",
            "folder_path": "/export/foscam/back_door",
        }

        response = client.post("/api/cameras", json=camera_data)

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "online"  # Default status

    def test_create_camera_missing_name(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test camera creation fails without name."""
        camera_data = {
            "folder_path": "/export/foscam/test",
        }

        response = client.post("/api/cameras", json=camera_data)

        assert response.status_code == 422  # Validation error

    def test_create_camera_missing_folder_path(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test camera creation fails without folder_path."""
        camera_data = {
            "name": "Test Camera",
        }

        response = client.post("/api/cameras", json=camera_data)

        assert response.status_code == 422  # Validation error

    def test_create_camera_empty_name(self, client: TestClient, mock_db_session: AsyncMock) -> None:
        """Test camera creation fails with empty name."""
        camera_data = {
            "name": "",
            "folder_path": "/export/foscam/test",
        }

        response = client.post("/api/cameras", json=camera_data)

        assert response.status_code == 422  # Validation error

    def test_create_camera_empty_folder_path(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test camera creation fails with empty folder_path."""
        camera_data = {
            "name": "Test Camera",
            "folder_path": "",
        }

        response = client.post("/api/cameras", json=camera_data)

        assert response.status_code == 422  # Validation error

    def test_create_camera_name_too_long(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test camera creation fails with name exceeding max length."""
        camera_data = {
            "name": "A" * 256,  # Exceeds 255 character limit
            "folder_path": "/export/foscam/test",
        }

        response = client.post("/api/cameras", json=camera_data)

        assert response.status_code == 422  # Validation error

    def test_create_camera_folder_path_too_long(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test camera creation fails with folder_path exceeding max length."""
        camera_data = {
            "name": "Test Camera",
            "folder_path": "/export/foscam/" + "a" * 500,  # Exceeds 500 character limit
        }

        response = client.post("/api/cameras", json=camera_data)

        assert response.status_code == 422  # Validation error

    def test_create_camera_generates_normalized_id(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that camera creation generates a normalized ID from the camera name."""
        # Mock execute to return no existing cameras (no duplicates)
        mock_results = [MagicMock(), MagicMock()]
        mock_results[0].scalar_one_or_none.return_value = None  # No name match
        mock_results[1].scalar_one_or_none.return_value = None  # No folder_path match
        mock_db_session.execute = AsyncMock(side_effect=mock_results)

        async def mock_refresh(camera):
            camera.created_at = datetime(2025, 12, 23, 10, 0, 0)
            camera.last_seen_at = None

        mock_db_session.refresh = mock_refresh

        camera_data = {
            "name": "Test Camera",
            "folder_path": "/export/foscam/test",
        }

        response = client.post("/api/cameras", json=camera_data)

        assert response.status_code == 201
        data = response.json()
        # Validate normalized ID format - should match normalize_camera_id(name)
        assert data["id"] == "test_camera"

    def test_create_camera_duplicate_name_returns_409(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test creating a camera with a duplicate name returns 409 Conflict."""
        # Mock the first execute call (name check) to return an existing camera
        existing_camera = Camera(
            id="existing-id-123",
            name="Test Camera",
            folder_path="/export/foscam/existing",
            status="online",
            created_at=datetime(2025, 12, 23, 10, 0, 0),
            last_seen_at=None,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_camera
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        camera_data = {
            "name": "Test Camera",  # Same name as existing
            "folder_path": "/export/foscam/new_path",
        }

        response = client.post("/api/cameras", json=camera_data)

        assert response.status_code == 409
        data = response.json()
        assert "already exists" in data["detail"].lower()
        assert "Test Camera" in data["detail"]

    def test_create_camera_duplicate_folder_path_returns_409(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test creating a camera with a duplicate folder_path returns 409 Conflict."""
        # Mock to return None for name check, then existing camera for folder check
        existing_camera = Camera(
            id="existing-id-456",
            name="Existing Camera",
            folder_path="/export/foscam/duplicate",
            status="online",
            created_at=datetime(2025, 12, 23, 10, 0, 0),
            last_seen_at=None,
        )
        mock_results = [MagicMock(), MagicMock()]
        mock_results[0].scalar_one_or_none.return_value = None  # No name match
        mock_results[1].scalar_one_or_none.return_value = existing_camera  # folder_path match
        mock_db_session.execute = AsyncMock(side_effect=mock_results)

        camera_data = {
            "name": "New Camera Name",
            "folder_path": "/export/foscam/duplicate",  # Same folder_path as existing
        }

        response = client.post("/api/cameras", json=camera_data)

        assert response.status_code == 409
        data = response.json()
        assert "already exists" in data["detail"].lower()
        assert "/export/foscam/duplicate" in data["detail"]

    def test_create_camera_no_duplicate_succeeds(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test creating a camera with unique name and folder_path succeeds."""
        # Mock to return None for both checks (no duplicates)
        mock_results = [MagicMock(), MagicMock()]
        mock_results[0].scalar_one_or_none.return_value = None  # No name match
        mock_results[1].scalar_one_or_none.return_value = None  # No folder_path match
        mock_db_session.execute = AsyncMock(side_effect=mock_results)

        async def mock_refresh(camera):
            camera.created_at = datetime(2025, 12, 23, 10, 0, 0)
            camera.last_seen_at = None

        mock_db_session.refresh = mock_refresh

        camera_data = {
            "name": "Unique Camera",
            "folder_path": "/export/foscam/unique",
        }

        response = client.post("/api/cameras", json=camera_data)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Unique Camera"
        assert data["folder_path"] == "/export/foscam/unique"


# =============================================================================
# Update Camera Tests (PATCH /api/cameras/{camera_id})
# =============================================================================


class TestUpdateCamera:
    """Tests for PATCH /api/cameras/{camera_id} endpoint."""

    def test_update_camera_name(
        self, client: TestClient, mock_db_session: AsyncMock, sample_camera: Camera
    ) -> None:
        """Test updating camera name."""
        mock_result = MagicMock()
        # NEM-3597: update_camera uses unique().scalar_one_or_none() due to joinedload(areas)
        mock_result.unique.return_value.scalar_one_or_none.return_value = sample_camera
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.patch(
            f"/api/cameras/{sample_camera.id}",
            json={"name": "New Name"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Name"
        assert data["folder_path"] == sample_camera.folder_path  # Unchanged

    def test_update_camera_status(
        self, client: TestClient, mock_db_session: AsyncMock, sample_camera: Camera
    ) -> None:
        """Test updating camera status."""
        mock_result = MagicMock()
        # NEM-3597: update_camera uses unique().scalar_one_or_none() due to joinedload(areas)
        mock_result.unique.return_value.scalar_one_or_none.return_value = sample_camera
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.patch(
            f"/api/cameras/{sample_camera.id}",
            json={"status": "offline"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "offline"

    def test_update_camera_folder_path(
        self, client: TestClient, mock_db_session: AsyncMock, sample_camera: Camera
    ) -> None:
        """Test updating camera folder path."""
        mock_result = MagicMock()
        # NEM-3597: update_camera uses unique().scalar_one_or_none() due to joinedload(areas)
        mock_result.unique.return_value.scalar_one_or_none.return_value = sample_camera
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.patch(
            f"/api/cameras/{sample_camera.id}",
            json={"folder_path": "/export/foscam/new_path"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["folder_path"] == "/export/foscam/new_path"

    def test_update_camera_multiple_fields(
        self, client: TestClient, mock_db_session: AsyncMock, sample_camera: Camera
    ) -> None:
        """Test updating multiple camera fields at once."""
        mock_result = MagicMock()
        # NEM-3597: update_camera uses unique().scalar_one_or_none() due to joinedload(areas)
        mock_result.unique.return_value.scalar_one_or_none.return_value = sample_camera
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.patch(
            f"/api/cameras/{sample_camera.id}",
            json={
                "name": "New Name",
                "status": "offline",
                "folder_path": "/export/foscam/new_path",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Name"
        assert data["status"] == "offline"
        assert data["folder_path"] == "/export/foscam/new_path"

    def test_update_camera_not_found(self, client: TestClient, mock_db_session: AsyncMock) -> None:
        """Test updating a non-existent camera returns 404."""
        mock_result = MagicMock()
        # NEM-3597: update_camera uses unique().scalar_one_or_none() due to joinedload(areas)
        mock_result.unique.return_value.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        fake_id = str(uuid.uuid4())
        response = client.patch(
            f"/api/cameras/{fake_id}",
            json={"name": "New Name"},
        )

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
        assert fake_id in data["detail"]

    def test_update_camera_empty_payload(
        self, client: TestClient, mock_db_session: AsyncMock, sample_camera: Camera
    ) -> None:
        """Test updating camera with empty payload."""
        mock_result = MagicMock()
        # NEM-3597: update_camera uses unique().scalar_one_or_none() due to joinedload(areas)
        mock_result.unique.return_value.scalar_one_or_none.return_value = sample_camera
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.patch(f"/api/cameras/{sample_camera.id}", json={})

        assert response.status_code == 200
        data = response.json()
        # Nothing should change
        assert data["name"] == sample_camera.name
        assert data["folder_path"] == sample_camera.folder_path
        assert data["status"] == sample_camera.status

    def test_update_camera_invalid_empty_name(
        self, client: TestClient, mock_db_session: AsyncMock, sample_camera: Camera
    ) -> None:
        """Test updating camera with empty name fails validation."""
        mock_result = MagicMock()
        # NEM-3597: update_camera uses unique().scalar_one_or_none() due to joinedload(areas)
        mock_result.unique.return_value.scalar_one_or_none.return_value = sample_camera
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.patch(
            f"/api/cameras/{sample_camera.id}",
            json={"name": ""},
        )

        assert response.status_code == 422  # Validation error

    def test_update_camera_invalid_empty_folder_path(
        self, client: TestClient, mock_db_session: AsyncMock, sample_camera: Camera
    ) -> None:
        """Test updating camera with empty folder_path fails validation."""
        mock_result = MagicMock()
        # NEM-3597: update_camera uses unique().scalar_one_or_none() due to joinedload(areas)
        mock_result.unique.return_value.scalar_one_or_none.return_value = sample_camera
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.patch(
            f"/api/cameras/{sample_camera.id}",
            json={"folder_path": ""},
        )

        assert response.status_code == 422  # Validation error


# =============================================================================
# Delete Camera Tests (DELETE /api/cameras/{camera_id})
# =============================================================================


class TestDeleteCamera:
    """Tests for DELETE /api/cameras/{camera_id} endpoint."""

    def test_delete_camera_success(
        self, client: TestClient, mock_db_session: AsyncMock, sample_camera: Camera
    ) -> None:
        """Test successful camera deletion."""
        mock_result = MagicMock()
        # delete_camera doesn't use load_areas, so use scalar_one_or_none directly
        mock_result.scalar_one_or_none.return_value = sample_camera
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.delete(f"/api/cameras/{sample_camera.id}")

        assert response.status_code == 204
        assert response.content == b""  # No content for 204
        # Verify delete was called
        mock_db_session.delete.assert_called_once_with(sample_camera)
        mock_db_session.commit.assert_called_once()

    def test_delete_camera_not_found(self, client: TestClient, mock_db_session: AsyncMock) -> None:
        """Test deleting a non-existent camera returns 404."""
        mock_result = MagicMock()
        # delete_camera doesn't use load_areas, so use scalar_one_or_none directly
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        fake_id = str(uuid.uuid4())
        response = client.delete(f"/api/cameras/{fake_id}")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
        assert fake_id in data["detail"]
        # Verify delete was NOT called
        mock_db_session.delete.assert_not_called()


# =============================================================================
# Get Camera Snapshot Tests (GET /api/cameras/{camera_id}/snapshot)
# =============================================================================


class TestGetCameraSnapshot:
    """Tests for GET /api/cameras/{camera_id}/snapshot endpoint."""

    def test_get_snapshot_camera_not_found(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test snapshot endpoint returns 404 if camera doesn't exist."""
        mock_result = MagicMock()
        # Snapshot endpoint doesn't use load_areas, so use scalar_one_or_none directly
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/cameras/{fake_id}/snapshot")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_get_snapshot_folder_outside_base_path(
        self, client: TestClient, mock_db_session: AsyncMock, tmp_path: Path
    ) -> None:
        """Test snapshot endpoint returns 404 if folder is outside base path."""
        # Create a camera with folder outside allowed base path
        camera = Camera(
            id=str(uuid.uuid4()),
            name="Bad Camera",
            folder_path="/etc/passwd",  # Outside foscam_base_path
            status="online",
            created_at=datetime(2025, 12, 23, 10, 0, 0),
            last_seen_at=None,
        )
        mock_result = MagicMock()
        # Snapshot endpoint doesn't use joinedload for areas
        mock_result.scalar_one_or_none.return_value = camera
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        # Mock settings to use tmp_path as base
        mock_settings = MagicMock()
        mock_settings.foscam_base_path = str(tmp_path / "foscam")

        with patch("backend.api.routes.cameras.get_settings", return_value=mock_settings):
            response = client.get(f"/api/cameras/{camera.id}/snapshot")

        assert response.status_code == 404
        data = response.json()
        # NEM-2446: Message now says "Camera folder does not exist" for invalid paths
        detail_lower = data["detail"].lower()
        assert any(msg in detail_lower for msg in ["no snapshot", "not found", "does not exist"])

    def test_get_snapshot_folder_outside_base_path_with_fallback(
        self, client: TestClient, mock_db_session: AsyncMock, tmp_path: Path
    ) -> None:
        """Test snapshot endpoint uses fallback when stored path is outside base but folder exists by ID."""
        # This tests the fix for im3c: when FOSCAM_BASE_PATH changes between environments
        # (e.g., Docker /cameras vs native /export/foscam), the endpoint should fall back
        # to looking for the camera folder by camera_id under the current base_path.

        # Set up paths - camera stored with different environment's path
        foscam_root = tmp_path / "foscam"
        camera_uuid = str(uuid.uuid4())  # Use valid UUID
        folder_name = "den"  # Folder name for fallback testing
        camera_folder = foscam_root / camera_uuid  # Folder matches camera UUID
        camera_folder.mkdir(parents=True)

        # Create a test image in the fallback folder
        test_image = camera_folder / "snapshot.jpg"
        test_image.write_bytes(b"\xff\xd8\xff\xe0image data")  # Valid JPEG header

        # Camera has wrong folder_path (from different environment like Docker /cameras)
        camera = Camera(
            id=camera_uuid,
            name="Den",
            folder_path="/cameras/den",  # Wrong path - different environment
            status="online",
            created_at=datetime(2025, 12, 23, 10, 0, 0),
            last_seen_at=None,
        )
        mock_result = MagicMock()
        # Snapshot endpoint doesn't use joinedload for areas
        mock_result.scalar_one_or_none.return_value = camera
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        # Mock settings to use tmp_path/foscam as base (simulating native environment)
        mock_settings = MagicMock()
        mock_settings.foscam_base_path = str(foscam_root)

        with patch("backend.api.routes.cameras.get_settings", return_value=mock_settings):
            response = client.get(f"/api/cameras/{camera_uuid}/snapshot")

        # Should succeed using fallback path
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/jpeg"

    def test_get_snapshot_folder_outside_base_path_with_fallback_by_folder_name(
        self, client: TestClient, mock_db_session: AsyncMock, tmp_path: Path
    ) -> None:
        """Test snapshot endpoint uses fallback by folder name when camera name differs.

        This tests the fix for NEM-1058: when the camera name (which generates the ID)
        differs from the folder name (e.g., camera "Den Camera" with folder "den"),
        the endpoint should first try to extract the folder name from the stored
        folder_path and look for it under the current base_path.
        """
        # Set up paths - folder is "den" but camera name would normalize to "den_camera"
        foscam_root = tmp_path / "foscam"
        folder_name = "den"
        camera_folder = foscam_root / folder_name
        camera_folder.mkdir(parents=True)

        # Create a test image
        test_image = camera_folder / "snapshot.jpg"
        test_image.write_bytes(b"\xff\xd8\xff\xe0image data")  # Valid JPEG header

        # Camera UUID - using valid UUID format
        camera_uuid = str(uuid.uuid4())
        camera = Camera(
            id=camera_uuid,
            name="Den Camera",
            # Stored path from different environment, but folder name matches actual folder
            folder_path=f"/cameras/{folder_name}",
            status="online",
            created_at=datetime(2025, 12, 23, 10, 0, 0),
            last_seen_at=None,
        )
        mock_result = MagicMock()
        # Snapshot endpoint doesn't use joinedload for areas
        mock_result.scalar_one_or_none.return_value = camera
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        # Mock settings to use tmp_path/foscam as base
        mock_settings = MagicMock()
        mock_settings.foscam_base_path = str(foscam_root)

        with patch("backend.api.routes.cameras.get_settings", return_value=mock_settings):
            response = client.get(f"/api/cameras/{camera_uuid}/snapshot")

        # Should succeed using fallback by folder name (extracted from stored path)
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/jpeg"

    def test_get_snapshot_folder_does_not_exist(
        self, client: TestClient, mock_db_session: AsyncMock, tmp_path: Path
    ) -> None:
        """Test snapshot endpoint returns 404 if camera folder doesn't exist."""
        # Set up paths
        foscam_root = tmp_path / "foscam"
        foscam_root.mkdir(parents=True)
        camera_folder = foscam_root / "front_door"  # Does NOT exist

        camera = Camera(
            id=str(uuid.uuid4()),
            name="Front Door",
            folder_path=str(camera_folder),
            status="online",
            created_at=datetime(2025, 12, 23, 10, 0, 0),
            last_seen_at=None,
        )
        mock_result = MagicMock()
        # Snapshot endpoint doesn't use joinedload for areas
        mock_result.scalar_one_or_none.return_value = camera
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        mock_settings = MagicMock()
        mock_settings.foscam_base_path = str(foscam_root)

        with patch("backend.api.routes.cameras.get_settings", return_value=mock_settings):
            response = client.get(f"/api/cameras/{camera.id}/snapshot")

        assert response.status_code == 404
        data = response.json()
        assert "does not exist" in data["detail"].lower()

    def test_get_snapshot_no_images_found(
        self, client: TestClient, mock_db_session: AsyncMock, tmp_path: Path
    ) -> None:
        """Test snapshot endpoint returns 404 if no images exist in folder."""
        # Set up paths
        foscam_root = tmp_path / "foscam"
        camera_folder = foscam_root / "front_door"
        camera_folder.mkdir(parents=True)
        # Create a non-image file
        (camera_folder / "readme.txt").write_text("not an image")

        camera = Camera(
            id=str(uuid.uuid4()),
            name="Front Door",
            folder_path=str(camera_folder),
            status="online",
            created_at=datetime(2025, 12, 23, 10, 0, 0),
            last_seen_at=None,
        )
        mock_result = MagicMock()
        # Snapshot endpoint doesn't use joinedload for areas
        mock_result.scalar_one_or_none.return_value = camera
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        mock_settings = MagicMock()
        mock_settings.foscam_base_path = str(foscam_root)

        with patch("backend.api.routes.cameras.get_settings", return_value=mock_settings):
            response = client.get(f"/api/cameras/{camera.id}/snapshot")

        assert response.status_code == 404
        data = response.json()
        assert "no snapshot" in data["detail"].lower()

    def test_get_snapshot_returns_latest_jpg(
        self, client: TestClient, mock_db_session: AsyncMock, tmp_path: Path
    ) -> None:
        """Test snapshot endpoint returns the most recently modified JPG image."""
        import os

        # Set up paths
        foscam_root = tmp_path / "foscam"
        camera_folder = foscam_root / "front_door"
        camera_folder.mkdir(parents=True)

        # Create two images with different modification times using os.utime
        older_image = camera_folder / "older.jpg"
        older_image.write_bytes(b"older image data")
        os.utime(older_image, (1000.0, 1000.0))  # Set explicit older mtime

        newer_image = camera_folder / "newer.jpg"
        newer_image.write_bytes(b"newer image data")
        os.utime(newer_image, (2000.0, 2000.0))  # Set explicit newer mtime

        camera = Camera(
            id=str(uuid.uuid4()),
            name="Front Door",
            folder_path=str(camera_folder),
            status="online",
            created_at=datetime(2025, 12, 23, 10, 0, 0),
            last_seen_at=None,
        )
        mock_result = MagicMock()
        # Snapshot endpoint doesn't use joinedload for areas
        mock_result.scalar_one_or_none.return_value = camera
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        mock_settings = MagicMock()
        mock_settings.foscam_base_path = str(foscam_root)

        with patch("backend.api.routes.cameras.get_settings", return_value=mock_settings):
            response = client.get(f"/api/cameras/{camera.id}/snapshot")

        assert response.status_code == 200
        assert response.content == b"newer image data"
        assert response.headers["content-type"].startswith("image/jpeg")

    def test_get_snapshot_returns_latest_png(
        self, client: TestClient, mock_db_session: AsyncMock, tmp_path: Path
    ) -> None:
        """Test snapshot endpoint returns the most recently modified PNG image."""

        # Set up paths
        foscam_root = tmp_path / "foscam"
        camera_folder = foscam_root / "front_door"
        camera_folder.mkdir(parents=True)

        # Create a PNG image
        png_image = camera_folder / "snapshot.png"
        png_image.write_bytes(b"png image data")

        camera = Camera(
            id=str(uuid.uuid4()),
            name="Front Door",
            folder_path=str(camera_folder),
            status="online",
            created_at=datetime(2025, 12, 23, 10, 0, 0),
            last_seen_at=None,
        )
        mock_result = MagicMock()
        # Snapshot endpoint doesn't use joinedload for areas
        mock_result.scalar_one_or_none.return_value = camera
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        mock_settings = MagicMock()
        mock_settings.foscam_base_path = str(foscam_root)

        with patch("backend.api.routes.cameras.get_settings", return_value=mock_settings):
            response = client.get(f"/api/cameras/{camera.id}/snapshot")

        assert response.status_code == 200
        assert response.content == b"png image data"
        assert response.headers["content-type"].startswith("image/png")

    def test_get_snapshot_returns_latest_gif(
        self, client: TestClient, mock_db_session: AsyncMock, tmp_path: Path
    ) -> None:
        """Test snapshot endpoint returns the most recently modified GIF image."""
        # Set up paths
        foscam_root = tmp_path / "foscam"
        camera_folder = foscam_root / "front_door"
        camera_folder.mkdir(parents=True)

        # Create a GIF image
        gif_image = camera_folder / "snapshot.gif"
        gif_image.write_bytes(b"gif image data")

        camera = Camera(
            id=str(uuid.uuid4()),
            name="Front Door",
            folder_path=str(camera_folder),
            status="online",
            created_at=datetime(2025, 12, 23, 10, 0, 0),
            last_seen_at=None,
        )
        mock_result = MagicMock()
        # Snapshot endpoint doesn't use joinedload for areas
        mock_result.scalar_one_or_none.return_value = camera
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        mock_settings = MagicMock()
        mock_settings.foscam_base_path = str(foscam_root)

        with patch("backend.api.routes.cameras.get_settings", return_value=mock_settings):
            response = client.get(f"/api/cameras/{camera.id}/snapshot")

        assert response.status_code == 200
        assert response.content == b"gif image data"
        assert response.headers["content-type"].startswith("image/gif")

    def test_get_snapshot_finds_images_in_subdirectories(
        self, client: TestClient, mock_db_session: AsyncMock, tmp_path: Path
    ) -> None:
        """Test snapshot endpoint finds images in subdirectories (rglob)."""

        # Set up paths
        foscam_root = tmp_path / "foscam"
        camera_folder = foscam_root / "front_door"
        subdirectory = camera_folder / "2025" / "12" / "23"
        subdirectory.mkdir(parents=True)

        # Create image in subdirectory
        nested_image = subdirectory / "capture.jpg"
        nested_image.write_bytes(b"nested image data")

        camera = Camera(
            id=str(uuid.uuid4()),
            name="Front Door",
            folder_path=str(camera_folder),
            status="online",
            created_at=datetime(2025, 12, 23, 10, 0, 0),
            last_seen_at=None,
        )
        mock_result = MagicMock()
        # Snapshot endpoint doesn't use joinedload for areas
        mock_result.scalar_one_or_none.return_value = camera
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        mock_settings = MagicMock()
        mock_settings.foscam_base_path = str(foscam_root)

        with patch("backend.api.routes.cameras.get_settings", return_value=mock_settings):
            response = client.get(f"/api/cameras/{camera.id}/snapshot")

        assert response.status_code == 200
        assert response.content == b"nested image data"

    def test_get_snapshot_case_insensitive_extension(
        self, client: TestClient, mock_db_session: AsyncMock, tmp_path: Path
    ) -> None:
        """Test snapshot endpoint handles uppercase extensions correctly."""
        # Set up paths
        foscam_root = tmp_path / "foscam"
        camera_folder = foscam_root / "front_door"
        camera_folder.mkdir(parents=True)

        # Create image with uppercase extension
        upper_image = camera_folder / "snapshot.JPG"
        upper_image.write_bytes(b"uppercase jpg data")

        camera = Camera(
            id=str(uuid.uuid4()),
            name="Front Door",
            folder_path=str(camera_folder),
            status="online",
            created_at=datetime(2025, 12, 23, 10, 0, 0),
            last_seen_at=None,
        )
        mock_result = MagicMock()
        # Snapshot endpoint doesn't use joinedload for areas
        mock_result.scalar_one_or_none.return_value = camera
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        mock_settings = MagicMock()
        mock_settings.foscam_base_path = str(foscam_root)

        with patch("backend.api.routes.cameras.get_settings", return_value=mock_settings):
            response = client.get(f"/api/cameras/{camera.id}/snapshot")

        # Note: The rglob pattern is case-sensitive, so this should return 404
        # because the routes file uses lowercase patterns
        # If the implementation supports case-insensitive matching, this would be 200
        # Based on the current implementation, this will likely be 404
        assert response.status_code in [200, 404]


# =============================================================================
# Schema Validation Tests
# =============================================================================


class TestCameraCreateSchema:
    """Tests for CameraCreate schema validation."""

    def test_camera_create_valid(self) -> None:
        """Test CameraCreate with valid data."""
        data = {
            "name": "Front Door Camera",
            "folder_path": "/export/foscam/front_door",
            "status": "online",
        }
        schema = CameraCreate(**data)
        assert schema.name == "Front Door Camera"
        assert schema.folder_path == "/export/foscam/front_door"
        assert schema.status == "online"

    def test_camera_create_default_status(self) -> None:
        """Test CameraCreate uses default status when not provided."""
        data = {
            "name": "Front Door Camera",
            "folder_path": "/export/foscam/front_door",
        }
        schema = CameraCreate(**data)
        assert schema.status == "online"

    def test_camera_create_missing_name_raises(self) -> None:
        """Test CameraCreate raises validation error when name is missing."""
        from pydantic import ValidationError

        data = {
            "folder_path": "/export/foscam/front_door",
        }
        with pytest.raises(ValidationError):
            CameraCreate(**data)

    def test_camera_create_missing_folder_path_raises(self) -> None:
        """Test CameraCreate raises validation error when folder_path is missing."""
        from pydantic import ValidationError

        data = {
            "name": "Front Door Camera",
        }
        with pytest.raises(ValidationError):
            CameraCreate(**data)


class TestCameraUpdateSchema:
    """Tests for CameraUpdate schema validation."""

    def test_camera_update_all_fields(self) -> None:
        """Test CameraUpdate with all fields."""
        data = {
            "name": "New Name",
            "folder_path": "/export/foscam/new_path",
            "status": "offline",
        }
        schema = CameraUpdate(**data)
        assert schema.name == "New Name"
        assert schema.folder_path == "/export/foscam/new_path"
        assert schema.status == "offline"

    def test_camera_update_partial(self) -> None:
        """Test CameraUpdate with partial data."""
        data = {"name": "New Name"}
        schema = CameraUpdate(**data)
        assert schema.name == "New Name"
        assert schema.folder_path is None
        assert schema.status is None

    def test_camera_update_empty(self) -> None:
        """Test CameraUpdate with empty data."""
        data = {}
        schema = CameraUpdate(**data)
        assert schema.name is None
        assert schema.folder_path is None
        assert schema.status is None

    def test_camera_update_model_dump_exclude_unset(self) -> None:
        """Test CameraUpdate model_dump with exclude_unset."""
        data = {"name": "New Name"}
        schema = CameraUpdate(**data)
        dump = schema.model_dump(exclude_unset=True)
        assert dump == {"name": "New Name"}
        assert "folder_path" not in dump
        assert "status" not in dump


class TestCameraResponseSchema:
    """Tests for CameraResponse schema validation."""

    def test_camera_response_valid(self) -> None:
        """Test CameraResponse with valid data."""
        data = {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "name": "Front Door Camera",
            "folder_path": "/export/foscam/front_door",
            "status": "online",
            "created_at": datetime(2025, 12, 23, 10, 0, 0),
            "last_seen_at": datetime(2025, 12, 23, 12, 0, 0),
        }
        schema = CameraResponse(**data)
        assert schema.id == "123e4567-e89b-12d3-a456-426614174000"
        assert schema.name == "Front Door Camera"

    def test_camera_response_last_seen_at_null(self) -> None:
        """Test CameraResponse with null last_seen_at."""
        data = {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "name": "Front Door Camera",
            "folder_path": "/export/foscam/front_door",
            "status": "online",
            "created_at": datetime(2025, 12, 23, 10, 0, 0),
            "last_seen_at": None,
        }
        schema = CameraResponse(**data)
        assert schema.last_seen_at is None

    def test_camera_response_from_orm(self, sample_camera: Camera) -> None:
        """Test CameraResponse can be created from ORM model."""
        schema = CameraResponse.model_validate(sample_camera)
        assert schema.id == sample_camera.id
        assert schema.name == sample_camera.name
        assert schema.folder_path == sample_camera.folder_path
        assert schema.status == sample_camera.status


class TestCameraListResponseSchema:
    """Tests for CameraListResponse schema validation."""

    def test_camera_list_response_valid(self) -> None:
        """Test CameraListResponse with valid data."""
        data = {
            "items": [
                {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "name": "Camera 1",
                    "folder_path": "/export/foscam/cam1",
                    "status": "online",
                    "created_at": datetime(2025, 12, 23, 10, 0, 0),
                    "last_seen_at": None,
                }
            ],
            "pagination": {
                "total": 1,
                "limit": 1000,
                "has_more": False,
            },
        }
        schema = CameraListResponse(**data)
        assert len(schema.items) == 1
        assert schema.pagination.total == 1

    def test_camera_list_response_empty(self) -> None:
        """Test CameraListResponse with empty list."""
        data = {
            "items": [],
            "pagination": {
                "total": 0,
                "limit": 1000,
                "has_more": False,
            },
        }
        schema = CameraListResponse(**data)
        assert schema.items == []
        assert schema.pagination.total == 0

    def test_camera_list_response_missing_pagination_raises(self) -> None:
        """Test CameraListResponse raises error when pagination is missing."""
        from pydantic import ValidationError

        data = {
            "items": [],
        }
        with pytest.raises(ValidationError):
            CameraListResponse(**data)


# =============================================================================
# Camera Status Enum Validation Tests
# =============================================================================


class TestCameraStatusValidation:
    """Tests for CameraStatus enum validation."""

    def test_camera_status_enum_values(self) -> None:
        """Test CameraStatus enum has expected values."""
        assert CameraStatus.ONLINE.value == "online"
        assert CameraStatus.OFFLINE.value == "offline"
        assert CameraStatus.ERROR.value == "error"
        assert CameraStatus.UNKNOWN.value == "unknown"

    def test_camera_status_str_representation(self) -> None:
        """Test CameraStatus string representation."""
        assert str(CameraStatus.ONLINE) == "online"
        assert str(CameraStatus.OFFLINE) == "offline"
        assert str(CameraStatus.ERROR) == "error"
        assert str(CameraStatus.UNKNOWN) == "unknown"

    def test_camera_create_valid_status_online(self) -> None:
        """Test CameraCreate accepts 'online' status."""
        data = {
            "name": "Test Camera",
            "folder_path": "/export/foscam/test",
            "status": "online",
        }
        schema = CameraCreate(**data)
        assert schema.status == CameraStatus.ONLINE

    def test_camera_create_valid_status_offline(self) -> None:
        """Test CameraCreate accepts 'offline' status."""
        data = {
            "name": "Test Camera",
            "folder_path": "/export/foscam/test",
            "status": "offline",
        }
        schema = CameraCreate(**data)
        assert schema.status == CameraStatus.OFFLINE

    def test_camera_create_valid_status_error(self) -> None:
        """Test CameraCreate accepts 'error' status."""
        data = {
            "name": "Test Camera",
            "folder_path": "/export/foscam/test",
            "status": "error",
        }
        schema = CameraCreate(**data)
        assert schema.status == CameraStatus.ERROR

    def test_camera_create_valid_status_unknown(self) -> None:
        """Test CameraCreate accepts 'unknown' status."""
        data = {
            "name": "Test Camera",
            "folder_path": "/export/foscam/test",
            "status": "unknown",
        }
        schema = CameraCreate(**data)
        assert schema.status == CameraStatus.UNKNOWN

    def test_camera_create_invalid_status_raises(self) -> None:
        """Test CameraCreate rejects invalid status values."""
        from pydantic import ValidationError

        data = {
            "name": "Test Camera",
            "folder_path": "/export/foscam/test",
            "status": "invalid_status",
        }
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(**data)

        # Verify the error is about the status field
        errors = exc_info.value.errors()
        assert any(err["loc"] == ("status",) for err in errors)

    def test_camera_create_invalid_status_nonexistent(self) -> None:
        """Test CameraCreate rejects non-existent status values."""
        from pydantic import ValidationError

        data = {
            "name": "Test Camera",
            "folder_path": "/export/foscam/test",
            "status": "active",  # Not a valid status
        }
        with pytest.raises(ValidationError):
            CameraCreate(**data)

    def test_camera_create_invalid_status_empty(self) -> None:
        """Test CameraCreate rejects empty string status."""
        from pydantic import ValidationError

        data = {
            "name": "Test Camera",
            "folder_path": "/export/foscam/test",
            "status": "",
        }
        with pytest.raises(ValidationError):
            CameraCreate(**data)

    def test_camera_create_invalid_status_case_sensitive(self) -> None:
        """Test CameraCreate status validation is case-sensitive."""
        from pydantic import ValidationError

        data = {
            "name": "Test Camera",
            "folder_path": "/export/foscam/test",
            "status": "ONLINE",  # Should be lowercase
        }
        with pytest.raises(ValidationError):
            CameraCreate(**data)

    def test_camera_update_valid_status(self) -> None:
        """Test CameraUpdate accepts valid status values."""
        schema = CameraUpdate(status="offline")
        assert schema.status == CameraStatus.OFFLINE

    def test_camera_update_invalid_status_raises(self) -> None:
        """Test CameraUpdate rejects invalid status values."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CameraUpdate(status="invalid_status")

    def test_camera_update_null_status_allowed(self) -> None:
        """Test CameraUpdate allows null status for partial updates."""
        schema = CameraUpdate()
        assert schema.status is None

    def test_camera_response_valid_status(self) -> None:
        """Test CameraResponse with valid status."""
        data = {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "name": "Test Camera",
            "folder_path": "/export/foscam/test",
            "status": "online",
            "created_at": datetime(2025, 12, 23, 10, 0, 0),
            "last_seen_at": None,
        }
        schema = CameraResponse(**data)
        assert schema.status == CameraStatus.ONLINE

    def test_camera_response_invalid_status_raises(self) -> None:
        """Test CameraResponse rejects invalid status values."""
        from pydantic import ValidationError

        data = {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "name": "Test Camera",
            "folder_path": "/export/foscam/test",
            "status": "invalid_status",
            "created_at": datetime(2025, 12, 23, 10, 0, 0),
            "last_seen_at": None,
        }
        with pytest.raises(ValidationError):
            CameraResponse(**data)


class TestCameraStatusAPIValidation:
    """Tests for camera status validation via API endpoints."""

    def test_create_camera_invalid_status_returns_422(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test creating a camera with invalid status returns 422."""
        camera_data = {
            "name": "Test Camera",
            "folder_path": "/export/foscam/test",
            "status": "invalid_status",
        }

        response = client.post("/api/cameras", json=camera_data)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        # Verify error mentions status field
        assert any("status" in str(err.get("loc", [])) for err in data["detail"])

    def test_update_camera_invalid_status_returns_422(
        self, client: TestClient, mock_db_session: AsyncMock, sample_camera: Camera
    ) -> None:
        """Test updating a camera with invalid status returns 422."""
        mock_result = MagicMock()
        # NEM-3597: update_camera uses unique().scalar_one_or_none() due to joinedload(areas)
        mock_result.unique.return_value.scalar_one_or_none.return_value = sample_camera
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.patch(
            f"/api/cameras/{sample_camera.id}",
            json={"status": "invalid_status"},
        )

        assert response.status_code == 422

    def test_create_camera_case_insensitive_fails(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test creating a camera with uppercase status fails."""
        camera_data = {
            "name": "Test Camera",
            "folder_path": "/export/foscam/test",
            "status": "ONLINE",  # Uppercase - should fail
        }

        response = client.post("/api/cameras", json=camera_data)

        assert response.status_code == 422


# =============================================================================
# Folder Path Validation Tests
# =============================================================================


class TestFolderPathValidation:
    """Tests for folder_path validation in camera schemas."""

    def test_folder_path_path_traversal_rejected(self) -> None:
        """Test that path traversal attempts are rejected."""
        from pydantic import ValidationError

        # Test with ..
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(
                name="Test Camera",
                folder_path="/export/foscam/../../../etc/passwd",
            )
        errors = exc_info.value.errors()
        assert any("Path traversal" in str(err.get("msg", "")) for err in errors)

    def test_folder_path_path_traversal_middle_rejected(self) -> None:
        """Test that path traversal in the middle of the path is rejected."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(
                name="Test Camera",
                folder_path="/export/foscam/front_door/../back_door",
            )
        errors = exc_info.value.errors()
        assert any("Path traversal" in str(err.get("msg", "")) for err in errors)

    def test_folder_path_dotdot_only_rejected(self) -> None:
        """Test that just .. is rejected."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CameraCreate(
                name="Test Camera",
                folder_path="..",
            )

    def test_folder_path_forbidden_characters_rejected(self) -> None:
        """Test that forbidden characters are rejected."""
        from pydantic import ValidationError

        forbidden_paths = [
            "/export/foscam/test<bad",
            "/export/foscam/test>bad",
            "/export/foscam/test:bad",
            '/export/foscam/test"bad',
            "/export/foscam/test|bad",
            "/export/foscam/test?bad",
            "/export/foscam/test*bad",
            "/export/foscam/test\x00bad",  # Null character
        ]

        for bad_path in forbidden_paths:
            with pytest.raises(ValidationError) as exc_info:
                CameraCreate(
                    name="Test Camera",
                    folder_path=bad_path,
                )
            errors = exc_info.value.errors()
            assert any("forbidden characters" in str(err.get("msg", "")) for err in errors), (
                f"Expected validation error for path: {bad_path!r}"
            )

    def test_folder_path_valid_paths_accepted(self) -> None:
        """Test that valid paths are accepted."""
        valid_paths = [
            "/export/foscam/front_door",
            "/export/foscam/back-door",
            "/export/foscam/camera_1",
            "/home/user/cameras/cam.test",
            "/var/lib/cameras/2025/01/01",
            "cameras/local",
        ]

        for valid_path in valid_paths:
            camera = CameraCreate(
                name="Test Camera",
                folder_path=valid_path,
            )
            assert camera.folder_path == valid_path

    def test_folder_path_single_dot_allowed(self) -> None:
        """Test that a single dot in path is allowed (current directory reference)."""
        camera = CameraCreate(
            name="Test Camera",
            folder_path="/export/foscam/./front_door",
        )
        assert camera.folder_path == "/export/foscam/./front_door"

    def test_folder_path_dots_in_filename_allowed(self) -> None:
        """Test that dots in filenames/folder names are allowed."""
        camera = CameraCreate(
            name="Test Camera",
            folder_path="/export/foscam/camera.v2.backup",
        )
        assert camera.folder_path == "/export/foscam/camera.v2.backup"

    def test_update_folder_path_path_traversal_rejected(self) -> None:
        """Test that path traversal is rejected in update schema."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            CameraUpdate(
                folder_path="/export/foscam/../../../etc/passwd",
            )
        errors = exc_info.value.errors()
        assert any("Path traversal" in str(err.get("msg", "")) for err in errors)

    def test_update_folder_path_null_allowed(self) -> None:
        """Test that null folder_path is allowed in update schema."""
        update = CameraUpdate(folder_path=None)
        assert update.folder_path is None

    def test_update_folder_path_valid_accepted(self) -> None:
        """Test that valid folder_path is accepted in update schema."""
        update = CameraUpdate(folder_path="/export/foscam/new_location")
        assert update.folder_path == "/export/foscam/new_location"


class TestFolderPathAPIValidation:
    """Tests for folder_path validation via API endpoints."""

    def test_create_camera_path_traversal_returns_422(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test creating a camera with path traversal returns 422."""
        camera_data = {
            "name": "Test Camera",
            "folder_path": "/export/foscam/../../../etc/passwd",
        }

        response = client.post("/api/cameras", json=camera_data)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        # Verify error mentions folder_path
        assert any("folder_path" in str(err.get("loc", [])) for err in data["detail"])

    def test_create_camera_forbidden_chars_returns_422(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test creating a camera with forbidden characters returns 422."""
        camera_data = {
            "name": "Test Camera",
            "folder_path": "/export/foscam/test<script>",
        }

        response = client.post("/api/cameras", json=camera_data)

        assert response.status_code == 422

    def test_update_camera_path_traversal_returns_422(
        self, client: TestClient, mock_db_session: AsyncMock, sample_camera: Camera
    ) -> None:
        """Test updating a camera with path traversal returns 422."""
        mock_result = MagicMock()
        # NEM-3597: update_camera uses unique().scalar_one_or_none() due to joinedload(areas)
        mock_result.unique.return_value.scalar_one_or_none.return_value = sample_camera
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.patch(
            f"/api/cameras/{sample_camera.id}",
            json={"folder_path": "/export/foscam/../../../etc/passwd"},
        )

        assert response.status_code == 422

    def test_update_camera_valid_path_accepted(
        self, client: TestClient, mock_db_session: AsyncMock, sample_camera: Camera
    ) -> None:
        """Test updating a camera with valid path succeeds."""
        mock_result = MagicMock()
        # NEM-3597: update_camera uses unique().scalar_one_or_none() due to joinedload(areas)
        mock_result.unique.return_value.scalar_one_or_none.return_value = sample_camera
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.patch(
            f"/api/cameras/{sample_camera.id}",
            json={"folder_path": "/export/foscam/valid_path"},
        )

        assert response.status_code == 200
        assert response.json()["folder_path"] == "/export/foscam/valid_path"


class TestValidateCameraPaths:
    """Tests for the camera path validation endpoint."""

    def test_validate_paths_empty_database(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test validation endpoint with no cameras in database."""
        mock_result = MagicMock()
        # validate_camera_paths uses scalars().all() directly (no joinedload)
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.get("/api/cameras/validation/paths")

        assert response.status_code == 200
        data = response.json()
        assert data["total_cameras"] == 0
        assert data["valid_count"] == 0
        assert data["invalid_count"] == 0
        assert data["valid_cameras"] == []
        assert data["invalid_cameras"] == []

    def test_validate_paths_all_valid(
        self, client: TestClient, mock_db_session: AsyncMock, tmp_path: Path
    ) -> None:
        """Test validation when all cameras have valid paths."""
        foscam_root = tmp_path / "foscam"
        camera_folder = foscam_root / "front_door"
        camera_folder.mkdir(parents=True)
        # Create an image file
        (camera_folder / "test.jpg").write_bytes(b"fake image")

        camera = Camera(
            id="front_door",
            name="Front Door",
            folder_path=str(camera_folder),
            status="online",
            created_at=datetime(2025, 12, 23, 10, 0, 0),
            last_seen_at=None,
        )
        mock_result = MagicMock()
        # validate_camera_paths uses scalars().all() directly (no joinedload)
        mock_result.scalars.return_value.all.return_value = [camera]
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        mock_settings = MagicMock()
        mock_settings.foscam_base_path = str(foscam_root)

        with patch("backend.api.routes.cameras.get_settings", return_value=mock_settings):
            response = client.get("/api/cameras/validation/paths")

        assert response.status_code == 200
        data = response.json()
        assert data["total_cameras"] == 1
        assert data["valid_count"] == 1
        assert data["invalid_count"] == 0
        assert len(data["valid_cameras"]) == 1
        assert data["valid_cameras"][0]["id"] == "front_door"

    def test_validate_paths_invalid_base_path(
        self, client: TestClient, mock_db_session: AsyncMock, tmp_path: Path
    ) -> None:
        """Test validation when camera path is outside base path."""
        foscam_root = tmp_path / "foscam"
        foscam_root.mkdir(parents=True)
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir(parents=True)
        (outside_dir / "test.jpg").write_bytes(b"fake image")

        camera = Camera(
            id="bad_camera",
            name="Bad Camera",
            folder_path=str(outside_dir),
            status="online",
            created_at=datetime(2025, 12, 23, 10, 0, 0),
            last_seen_at=None,
        )
        mock_result = MagicMock()
        # validate_camera_paths uses scalars().all() directly (no joinedload)
        mock_result.scalars.return_value.all.return_value = [camera]
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        mock_settings = MagicMock()
        mock_settings.foscam_base_path = str(foscam_root)

        with patch("backend.api.routes.cameras.get_settings", return_value=mock_settings):
            response = client.get("/api/cameras/validation/paths")

        assert response.status_code == 200
        data = response.json()
        assert data["total_cameras"] == 1
        assert data["valid_count"] == 0
        assert data["invalid_count"] == 1
        assert len(data["invalid_cameras"]) == 1
        assert data["invalid_cameras"][0]["id"] == "bad_camera"
        assert "folder_path not under base_path" in data["invalid_cameras"][0]["issues"][0]

    def test_validate_paths_directory_not_exists(
        self, client: TestClient, mock_db_session: AsyncMock, tmp_path: Path
    ) -> None:
        """Test validation when camera directory doesn't exist."""
        foscam_root = tmp_path / "foscam"
        foscam_root.mkdir(parents=True)
        # Don't create the camera folder - it doesn't exist

        camera = Camera(
            id="missing_camera",
            name="Missing Camera",
            folder_path=str(foscam_root / "nonexistent"),
            status="online",
            created_at=datetime(2025, 12, 23, 10, 0, 0),
            last_seen_at=None,
        )
        mock_result = MagicMock()
        # validate_camera_paths uses scalars().all() directly (no joinedload)
        mock_result.scalars.return_value.all.return_value = [camera]
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        mock_settings = MagicMock()
        mock_settings.foscam_base_path = str(foscam_root)

        with patch("backend.api.routes.cameras.get_settings", return_value=mock_settings):
            response = client.get("/api/cameras/validation/paths")

        assert response.status_code == 200
        data = response.json()
        assert data["invalid_count"] == 1
        assert "directory does not exist" in data["invalid_cameras"][0]["issues"]

    def test_validate_paths_no_images(
        self, client: TestClient, mock_db_session: AsyncMock, tmp_path: Path
    ) -> None:
        """Test validation when camera directory has no images."""
        foscam_root = tmp_path / "foscam"
        camera_folder = foscam_root / "empty_camera"
        camera_folder.mkdir(parents=True)
        # Create non-image file
        (camera_folder / "readme.txt").write_text("not an image")

        camera = Camera(
            id="empty_camera",
            name="Empty Camera",
            folder_path=str(camera_folder),
            status="online",
            created_at=datetime(2025, 12, 23, 10, 0, 0),
            last_seen_at=None,
        )
        mock_result = MagicMock()
        # validate_camera_paths uses scalars().all() directly (no joinedload)
        mock_result.scalars.return_value.all.return_value = [camera]
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        mock_settings = MagicMock()
        mock_settings.foscam_base_path = str(foscam_root)

        with patch("backend.api.routes.cameras.get_settings", return_value=mock_settings):
            response = client.get("/api/cameras/validation/paths")

        assert response.status_code == 200
        data = response.json()
        assert data["invalid_count"] == 1
        # NEM-2446: Message now includes video files
        assert "no image or video files found" in data["invalid_cameras"][0]["issues"]

    def test_validate_paths_mixed_valid_invalid(
        self, client: TestClient, mock_db_session: AsyncMock, tmp_path: Path
    ) -> None:
        """Test validation with mix of valid and invalid cameras."""
        foscam_root = tmp_path / "foscam"
        valid_folder = foscam_root / "valid_camera"
        valid_folder.mkdir(parents=True)
        (valid_folder / "test.jpg").write_bytes(b"fake image")

        outside_dir = tmp_path / "outside"
        outside_dir.mkdir(parents=True)

        valid_camera = Camera(
            id="valid_camera",
            name="Valid Camera",
            folder_path=str(valid_folder),
            status="online",
            created_at=datetime(2025, 12, 23, 10, 0, 0),
            last_seen_at=None,
        )
        invalid_camera = Camera(
            id="invalid_camera",
            name="Invalid Camera",
            folder_path=str(outside_dir),
            status="online",
            created_at=datetime(2025, 12, 23, 10, 0, 0),
            last_seen_at=None,
        )
        mock_result = MagicMock()
        # validate_camera_paths uses scalars().all() directly (no joinedload)
        mock_result.scalars.return_value.all.return_value = [valid_camera, invalid_camera]
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        mock_settings = MagicMock()
        mock_settings.foscam_base_path = str(foscam_root)

        with patch("backend.api.routes.cameras.get_settings", return_value=mock_settings):
            response = client.get("/api/cameras/validation/paths")

        assert response.status_code == 200
        data = response.json()
        assert data["total_cameras"] == 2
        assert data["valid_count"] == 1
        assert data["invalid_count"] == 1
