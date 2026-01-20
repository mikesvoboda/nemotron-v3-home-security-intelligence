"""Unit tests for zones API routes.

Tests cover:
- GET /api/cameras/{camera_id}/zones - List zones for a camera
- POST /api/cameras/{camera_id}/zones - Create zone
- GET /api/cameras/{camera_id}/zones/{zone_id} - Get zone
- PUT /api/cameras/{camera_id}/zones/{zone_id} - Update zone
- DELETE /api/cameras/{camera_id}/zones/{zone_id} - Delete zone
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes.zones import router
from backend.api.schemas.zone import ZoneCreate, ZoneListResponse, ZoneResponse, ZoneUpdate
from backend.core.database import get_db
from backend.models.camera import Camera
from backend.models.camera_zone import CameraZone, CameraZoneShape, CameraZoneType

# Aliases for backward compatibility
Zone = CameraZone
ZoneShape = CameraZoneShape
ZoneType = CameraZoneType

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
def client(mock_db_session: AsyncMock) -> TestClient:
    """Create a test client with mocked dependencies."""
    app = FastAPI()
    app.include_router(router)

    # Override the database dependency
    async def override_get_db():
        yield mock_db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client


# Fixed UUIDs for consistent testing
SAMPLE_CAMERA_UUID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
SAMPLE_ZONE_UUID = "b2c3d4e5-f6a7-8901-bcde-f12345678901"
NONEXISTENT_CAMERA_UUID = "c3d4e5f6-a7b8-9012-cdef-123456789012"
NONEXISTENT_ZONE_UUID = "d4e5f6a7-b8c9-0123-defa-234567890123"


@pytest.fixture
def sample_camera() -> Camera:
    """Create a sample camera object for testing."""
    camera = Camera(
        id=SAMPLE_CAMERA_UUID,
        name="Front Door Camera",
        folder_path="/export/foscam/front_door",
        status="online",
        created_at=datetime(2025, 12, 23, 10, 0, 0),
        last_seen_at=datetime(2025, 12, 23, 12, 0, 0),
    )
    return camera


@pytest.fixture
def sample_zone() -> Zone:
    """Create a sample zone object for testing."""
    zone = Zone(
        id=SAMPLE_ZONE_UUID,
        camera_id=SAMPLE_CAMERA_UUID,
        name="Front Door Entry",
        zone_type=ZoneType.ENTRY_POINT,
        coordinates=[[0.1, 0.2], [0.3, 0.2], [0.3, 0.8], [0.1, 0.8]],
        shape=ZoneShape.RECTANGLE,
        color="#3B82F6",
        enabled=True,
        priority=1,
        created_at=datetime(2025, 12, 23, 10, 0, 0),
        updated_at=datetime(2025, 12, 23, 10, 0, 0),
    )
    return zone


@pytest.fixture
def sample_zone_list() -> list[Zone]:
    """Create a list of sample zones for testing."""
    return [
        Zone(
            id=str(uuid.uuid4()),
            camera_id=SAMPLE_CAMERA_UUID,
            name="Entry Zone",
            zone_type=ZoneType.ENTRY_POINT,
            coordinates=[[0.1, 0.1], [0.4, 0.1], [0.4, 0.4], [0.1, 0.4]],
            shape=ZoneShape.RECTANGLE,
            color="#3B82F6",
            enabled=True,
            priority=2,
            created_at=datetime(2025, 12, 23, 10, 0, 0),
            updated_at=datetime(2025, 12, 23, 10, 0, 0),
        ),
        Zone(
            id=str(uuid.uuid4()),
            camera_id=SAMPLE_CAMERA_UUID,
            name="Driveway Zone",
            zone_type=ZoneType.DRIVEWAY,
            coordinates=[[0.5, 0.5], [0.9, 0.5], [0.9, 0.9], [0.5, 0.9]],
            shape=ZoneShape.RECTANGLE,
            color="#EF4444",
            enabled=True,
            priority=1,
            created_at=datetime(2025, 12, 23, 10, 0, 0),
            updated_at=datetime(2025, 12, 23, 10, 0, 0),
        ),
        Zone(
            id=str(uuid.uuid4()),
            camera_id=SAMPLE_CAMERA_UUID,
            name="Disabled Zone",
            zone_type=ZoneType.OTHER,
            coordinates=[[0.0, 0.0], [0.2, 0.0], [0.2, 0.2], [0.0, 0.2]],
            shape=ZoneShape.RECTANGLE,
            color="#6B7280",
            enabled=False,
            priority=0,
            created_at=datetime(2025, 12, 23, 10, 0, 0),
            updated_at=datetime(2025, 12, 23, 10, 0, 0),
        ),
    ]


# =============================================================================
# List Zones Tests (GET /api/cameras/{camera_id}/zones)
# =============================================================================


class TestListZones:
    """Tests for GET /api/cameras/{camera_id}/zones endpoint."""

    def test_list_zones_empty(
        self, client: TestClient, mock_db_session: AsyncMock, sample_camera: Camera
    ) -> None:
        """Test listing zones when none exist."""
        # Mock camera lookup
        camera_result = MagicMock()
        camera_result.scalar_one_or_none.return_value = sample_camera

        # Mock zones lookup
        zones_result = MagicMock()
        zones_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(side_effect=[camera_result, zones_result])

        response = client.get(f"/api/cameras/{sample_camera.id}/zones")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["pagination"]["total"] == 0

    def test_list_zones_with_data(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_camera: Camera,
        sample_zone_list: list[Zone],
    ) -> None:
        """Test listing zones with existing data."""
        # Mock camera lookup
        camera_result = MagicMock()
        camera_result.scalar_one_or_none.return_value = sample_camera

        # Mock zones lookup
        zones_result = MagicMock()
        zones_result.scalars.return_value.all.return_value = sample_zone_list

        mock_db_session.execute = AsyncMock(side_effect=[camera_result, zones_result])

        response = client.get(f"/api/cameras/{sample_camera.id}/zones")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        assert data["pagination"]["total"] == 3

    def test_list_zones_filter_enabled(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_camera: Camera,
        sample_zone_list: list[Zone],
    ) -> None:
        """Test listing zones filtered by enabled status."""
        # Mock camera lookup
        camera_result = MagicMock()
        camera_result.scalar_one_or_none.return_value = sample_camera

        # Filter to only return enabled zones
        enabled_zones = [z for z in sample_zone_list if z.enabled]
        zones_result = MagicMock()
        zones_result.scalars.return_value.all.return_value = enabled_zones

        mock_db_session.execute = AsyncMock(side_effect=[camera_result, zones_result])

        response = client.get(f"/api/cameras/{sample_camera.id}/zones?enabled=true")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["pagination"]["total"] == 2
        # All returned zones should be enabled
        for zone in data["items"]:
            assert zone["enabled"] is True

    def test_list_zones_camera_not_found(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test listing zones for non-existent camera returns 404."""
        # Mock camera lookup - return None
        camera_result = MagicMock()
        camera_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=camera_result)

        response = client.get(f"/api/cameras/{NONEXISTENT_CAMERA_UUID}/zones")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()


# =============================================================================
# Create Zone Tests (POST /api/cameras/{camera_id}/zones)
# =============================================================================


class TestCreateZone:
    """Tests for POST /api/cameras/{camera_id}/zones endpoint."""

    def test_create_zone_success(
        self, client: TestClient, mock_db_session: AsyncMock, sample_camera: Camera
    ) -> None:
        """Test successful zone creation."""
        # Mock camera lookup
        camera_result = MagicMock()
        camera_result.scalar_one_or_none.return_value = sample_camera
        mock_db_session.execute = AsyncMock(return_value=camera_result)

        async def mock_refresh(zone):
            zone.created_at = datetime(2025, 12, 23, 10, 0, 0)
            zone.updated_at = datetime(2025, 12, 23, 10, 0, 0)

        mock_db_session.refresh = mock_refresh

        zone_data = {
            "name": "Front Door",
            "zone_type": "entry_point",
            "coordinates": [[0.1, 0.2], [0.3, 0.2], [0.3, 0.8], [0.1, 0.8]],
            "shape": "rectangle",
            "color": "#3B82F6",
            "enabled": True,
            "priority": 1,
        }

        response = client.post(f"/api/cameras/{sample_camera.id}/zones", json=zone_data)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == zone_data["name"]
        assert data["zone_type"] == zone_data["zone_type"]
        assert data["coordinates"] == zone_data["coordinates"]
        assert data["camera_id"] == sample_camera.id
        assert "id" in data
        # Validate UUID format
        uuid.UUID(data["id"])

    def test_create_zone_default_values(
        self, client: TestClient, mock_db_session: AsyncMock, sample_camera: Camera
    ) -> None:
        """Test zone creation with default values."""
        # Mock camera lookup
        camera_result = MagicMock()
        camera_result.scalar_one_or_none.return_value = sample_camera
        mock_db_session.execute = AsyncMock(return_value=camera_result)

        async def mock_refresh(zone):
            zone.created_at = datetime(2025, 12, 23, 10, 0, 0)
            zone.updated_at = datetime(2025, 12, 23, 10, 0, 0)

        mock_db_session.refresh = mock_refresh

        # Minimal data - only required fields
        zone_data = {
            "name": "Test Zone",
            "coordinates": [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2], [0.1, 0.2]],
        }

        response = client.post(f"/api/cameras/{sample_camera.id}/zones", json=zone_data)

        assert response.status_code == 201
        data = response.json()
        assert data["zone_type"] == "other"  # Default
        assert data["shape"] == "rectangle"  # Default
        assert data["color"] == "#3B82F6"  # Default
        assert data["enabled"] is True  # Default
        assert data["priority"] == 0  # Default

    def test_create_zone_camera_not_found(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test zone creation for non-existent camera returns 404."""
        camera_result = MagicMock()
        camera_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=camera_result)

        zone_data = {
            "name": "Test Zone",
            "coordinates": [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2], [0.1, 0.2]],
        }

        response = client.post(f"/api/cameras/{NONEXISTENT_CAMERA_UUID}/zones", json=zone_data)

        assert response.status_code == 404

    def test_create_zone_invalid_coordinates_not_normalized(
        self, client: TestClient, mock_db_session: AsyncMock, sample_camera: Camera
    ) -> None:
        """Test zone creation fails with non-normalized coordinates."""
        camera_result = MagicMock()
        camera_result.scalar_one_or_none.return_value = sample_camera
        mock_db_session.execute = AsyncMock(return_value=camera_result)

        zone_data = {
            "name": "Test Zone",
            "coordinates": [[0.1, 0.1], [1.5, 0.1], [0.2, 0.2]],  # 1.5 is out of range
        }

        response = client.post(f"/api/cameras/{sample_camera.id}/zones", json=zone_data)

        assert response.status_code == 422

    def test_create_zone_invalid_coordinates_wrong_format(
        self, client: TestClient, mock_db_session: AsyncMock, sample_camera: Camera
    ) -> None:
        """Test zone creation fails with wrong coordinate format."""
        camera_result = MagicMock()
        camera_result.scalar_one_or_none.return_value = sample_camera
        mock_db_session.execute = AsyncMock(return_value=camera_result)

        zone_data = {
            "name": "Test Zone",
            "coordinates": [[0.1, 0.1, 0.5], [0.2, 0.1], [0.2, 0.2]],  # 3 values
        }

        response = client.post(f"/api/cameras/{sample_camera.id}/zones", json=zone_data)

        assert response.status_code == 422

    def test_create_zone_too_few_points(
        self, client: TestClient, mock_db_session: AsyncMock, sample_camera: Camera
    ) -> None:
        """Test zone creation fails with fewer than 3 points."""
        camera_result = MagicMock()
        camera_result.scalar_one_or_none.return_value = sample_camera
        mock_db_session.execute = AsyncMock(return_value=camera_result)

        zone_data = {
            "name": "Test Zone",
            "coordinates": [[0.1, 0.1], [0.2, 0.1]],  # Only 2 points
        }

        response = client.post(f"/api/cameras/{sample_camera.id}/zones", json=zone_data)

        assert response.status_code == 422

    def test_create_zone_invalid_color(
        self, client: TestClient, mock_db_session: AsyncMock, sample_camera: Camera
    ) -> None:
        """Test zone creation fails with invalid hex color."""
        camera_result = MagicMock()
        camera_result.scalar_one_or_none.return_value = sample_camera
        mock_db_session.execute = AsyncMock(return_value=camera_result)

        zone_data = {
            "name": "Test Zone",
            "coordinates": [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2]],
            "color": "red",  # Not hex format
        }

        response = client.post(f"/api/cameras/{sample_camera.id}/zones", json=zone_data)

        assert response.status_code == 422


# =============================================================================
# Get Zone Tests (GET /api/cameras/{camera_id}/zones/{zone_id})
# =============================================================================


class TestGetZone:
    """Tests for GET /api/cameras/{camera_id}/zones/{zone_id} endpoint."""

    def test_get_zone_success(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_camera: Camera,
        sample_zone: Zone,
    ) -> None:
        """Test getting a specific zone by ID."""
        # Mock camera lookup
        camera_result = MagicMock()
        camera_result.scalar_one_or_none.return_value = sample_camera

        # Mock zone lookup
        zone_result = MagicMock()
        zone_result.scalar_one_or_none.return_value = sample_zone

        mock_db_session.execute = AsyncMock(side_effect=[camera_result, zone_result])

        response = client.get(f"/api/cameras/{sample_camera.id}/zones/{sample_zone.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_zone.id
        assert data["name"] == sample_zone.name
        assert data["camera_id"] == sample_zone.camera_id

    def test_get_zone_not_found(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_camera: Camera,
    ) -> None:
        """Test getting a non-existent zone returns 404."""
        # Mock camera lookup
        camera_result = MagicMock()
        camera_result.scalar_one_or_none.return_value = sample_camera

        # Mock zone lookup - return None
        zone_result = MagicMock()
        zone_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(side_effect=[camera_result, zone_result])

        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/cameras/{sample_camera.id}/zones/{fake_id}")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_get_zone_camera_not_found(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test getting zone for non-existent camera returns 404."""
        camera_result = MagicMock()
        camera_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=camera_result)

        response = client.get(
            f"/api/cameras/{NONEXISTENT_CAMERA_UUID}/zones/{NONEXISTENT_ZONE_UUID}"
        )

        assert response.status_code == 404


# =============================================================================
# Update Zone Tests (PUT /api/cameras/{camera_id}/zones/{zone_id})
# =============================================================================


class TestUpdateZone:
    """Tests for PUT /api/cameras/{camera_id}/zones/{zone_id} endpoint."""

    def test_update_zone_name(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_camera: Camera,
        sample_zone: Zone,
    ) -> None:
        """Test updating zone name."""
        # Mock camera lookup
        camera_result = MagicMock()
        camera_result.scalar_one_or_none.return_value = sample_camera

        # Mock zone lookup
        zone_result = MagicMock()
        zone_result.scalar_one_or_none.return_value = sample_zone

        mock_db_session.execute = AsyncMock(side_effect=[camera_result, zone_result])

        response = client.put(
            f"/api/cameras/{sample_camera.id}/zones/{sample_zone.id}",
            json={"name": "New Name"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Name"

    def test_update_zone_enabled(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_camera: Camera,
        sample_zone: Zone,
    ) -> None:
        """Test updating zone enabled status."""
        camera_result = MagicMock()
        camera_result.scalar_one_or_none.return_value = sample_camera

        zone_result = MagicMock()
        zone_result.scalar_one_or_none.return_value = sample_zone

        mock_db_session.execute = AsyncMock(side_effect=[camera_result, zone_result])

        response = client.put(
            f"/api/cameras/{sample_camera.id}/zones/{sample_zone.id}",
            json={"enabled": False},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False

    def test_update_zone_coordinates(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_camera: Camera,
        sample_zone: Zone,
    ) -> None:
        """Test updating zone coordinates."""
        camera_result = MagicMock()
        camera_result.scalar_one_or_none.return_value = sample_camera

        zone_result = MagicMock()
        zone_result.scalar_one_or_none.return_value = sample_zone

        mock_db_session.execute = AsyncMock(side_effect=[camera_result, zone_result])

        new_coords = [[0.2, 0.3], [0.5, 0.3], [0.5, 0.7], [0.2, 0.7]]
        response = client.put(
            f"/api/cameras/{sample_camera.id}/zones/{sample_zone.id}",
            json={"coordinates": new_coords},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["coordinates"] == new_coords

    def test_update_zone_not_found(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_camera: Camera,
    ) -> None:
        """Test updating non-existent zone returns 404."""
        camera_result = MagicMock()
        camera_result.scalar_one_or_none.return_value = sample_camera

        zone_result = MagicMock()
        zone_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(side_effect=[camera_result, zone_result])

        fake_id = str(uuid.uuid4())
        response = client.put(
            f"/api/cameras/{sample_camera.id}/zones/{fake_id}",
            json={"name": "New Name"},
        )

        assert response.status_code == 404

    def test_update_zone_invalid_coordinates(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_camera: Camera,
        sample_zone: Zone,
    ) -> None:
        """Test updating with invalid coordinates fails validation."""
        camera_result = MagicMock()
        camera_result.scalar_one_or_none.return_value = sample_camera

        zone_result = MagicMock()
        zone_result.scalar_one_or_none.return_value = sample_zone

        mock_db_session.execute = AsyncMock(side_effect=[camera_result, zone_result])

        response = client.put(
            f"/api/cameras/{sample_camera.id}/zones/{sample_zone.id}",
            json={"coordinates": [[1.5, 0.5], [0.5, 0.5], [0.5, 1.5]]},  # Out of range
        )

        assert response.status_code == 422


# =============================================================================
# Delete Zone Tests (DELETE /api/cameras/{camera_id}/zones/{zone_id})
# =============================================================================


class TestDeleteZone:
    """Tests for DELETE /api/cameras/{camera_id}/zones/{zone_id} endpoint."""

    def test_delete_zone_success(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_camera: Camera,
        sample_zone: Zone,
    ) -> None:
        """Test successful zone deletion."""
        camera_result = MagicMock()
        camera_result.scalar_one_or_none.return_value = sample_camera

        zone_result = MagicMock()
        zone_result.scalar_one_or_none.return_value = sample_zone

        mock_db_session.execute = AsyncMock(side_effect=[camera_result, zone_result])

        response = client.delete(f"/api/cameras/{sample_camera.id}/zones/{sample_zone.id}")

        assert response.status_code == 204
        assert response.content == b""
        mock_db_session.delete.assert_called_once_with(sample_zone)
        mock_db_session.commit.assert_called_once()

    def test_delete_zone_not_found(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_camera: Camera,
    ) -> None:
        """Test deleting non-existent zone returns 404."""
        camera_result = MagicMock()
        camera_result.scalar_one_or_none.return_value = sample_camera

        zone_result = MagicMock()
        zone_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(side_effect=[camera_result, zone_result])

        fake_id = str(uuid.uuid4())
        response = client.delete(f"/api/cameras/{sample_camera.id}/zones/{fake_id}")

        assert response.status_code == 404
        mock_db_session.delete.assert_not_called()

    def test_delete_zone_camera_not_found(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test deleting zone for non-existent camera returns 404."""
        camera_result = MagicMock()
        camera_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=camera_result)

        response = client.delete(
            f"/api/cameras/{NONEXISTENT_CAMERA_UUID}/zones/{NONEXISTENT_ZONE_UUID}"
        )

        assert response.status_code == 404


# =============================================================================
# Schema Validation Tests
# =============================================================================


class TestZoneCreateSchema:
    """Tests for ZoneCreate schema validation."""

    def test_zone_create_valid(self) -> None:
        """Test ZoneCreate with valid data."""
        data = {
            "name": "Front Door",
            "zone_type": "entry_point",
            "coordinates": [[0.1, 0.2], [0.3, 0.2], [0.3, 0.8], [0.1, 0.8]],
            "shape": "rectangle",
            "color": "#3B82F6",
            "enabled": True,
            "priority": 1,
        }
        schema = ZoneCreate(**data)
        assert schema.name == "Front Door"
        assert schema.zone_type == ZoneType.ENTRY_POINT
        assert len(schema.coordinates) == 4

    def test_zone_create_defaults(self) -> None:
        """Test ZoneCreate uses defaults."""
        data = {
            "name": "Test Zone",
            "coordinates": [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2]],
        }
        schema = ZoneCreate(**data)
        assert schema.zone_type == ZoneType.OTHER
        assert schema.shape == ZoneShape.RECTANGLE
        assert schema.color == "#3B82F6"
        assert schema.enabled is True
        assert schema.priority == 0

    def test_zone_create_invalid_coordinates_raises(self) -> None:
        """Test ZoneCreate raises error for invalid coordinates."""
        from pydantic import ValidationError

        data = {
            "name": "Test Zone",
            "coordinates": [[1.5, 0.5], [0.5, 0.5]],  # Out of range and too few
        }
        with pytest.raises(ValidationError):
            ZoneCreate(**data)


class TestZoneUpdateSchema:
    """Tests for ZoneUpdate schema validation."""

    def test_zone_update_all_fields(self) -> None:
        """Test ZoneUpdate with all fields."""
        data = {
            "name": "New Name",
            "zone_type": "driveway",
            "enabled": False,
        }
        schema = ZoneUpdate(**data)
        assert schema.name == "New Name"
        assert schema.zone_type == ZoneType.DRIVEWAY
        assert schema.enabled is False

    def test_zone_update_partial(self) -> None:
        """Test ZoneUpdate with partial data."""
        data = {"name": "New Name"}
        schema = ZoneUpdate(**data)
        assert schema.name == "New Name"
        assert schema.enabled is None
        assert schema.coordinates is None

    def test_zone_update_empty(self) -> None:
        """Test ZoneUpdate with empty data."""
        data = {}
        schema = ZoneUpdate(**data)
        assert schema.name is None
        assert schema.zone_type is None
        assert schema.coordinates is None


class TestZoneResponseSchema:
    """Tests for ZoneResponse schema validation."""

    def test_zone_response_valid(self) -> None:
        """Test ZoneResponse with valid data."""
        data = {
            "id": "zone-123",
            "camera_id": "front_door",
            "name": "Front Door",
            "zone_type": "entry_point",
            "coordinates": [[0.1, 0.2], [0.3, 0.2], [0.3, 0.8], [0.1, 0.8]],
            "shape": "rectangle",
            "color": "#3B82F6",
            "enabled": True,
            "priority": 1,
            "created_at": datetime(2025, 12, 23, 10, 0, 0),
            "updated_at": datetime(2025, 12, 23, 10, 0, 0),
        }
        schema = ZoneResponse(**data)
        assert schema.id == "zone-123"
        assert schema.name == "Front Door"

    def test_zone_response_from_orm(self, sample_zone: Zone) -> None:
        """Test ZoneResponse can be created from ORM model."""
        schema = ZoneResponse.model_validate(sample_zone)
        assert schema.id == sample_zone.id
        assert schema.name == sample_zone.name


class TestZoneListResponseSchema:
    """Tests for ZoneListResponse schema validation."""

    def test_zone_list_response_valid(self) -> None:
        """Test ZoneListResponse with valid data."""
        data = {
            "items": [
                {
                    "id": "zone-123",
                    "camera_id": "front_door",
                    "name": "Front Door",
                    "zone_type": "entry_point",
                    "coordinates": [[0.1, 0.2], [0.3, 0.2], [0.3, 0.8], [0.1, 0.8]],
                    "shape": "rectangle",
                    "color": "#3B82F6",
                    "enabled": True,
                    "priority": 1,
                    "created_at": datetime(2025, 12, 23, 10, 0, 0),
                    "updated_at": datetime(2025, 12, 23, 10, 0, 0),
                }
            ],
            "pagination": {"total": 1, "limit": 50, "offset": 0, "has_more": False},
        }
        schema = ZoneListResponse(**data)
        assert len(schema.items) == 1
        assert schema.pagination.total == 1

    def test_zone_list_response_empty(self) -> None:
        """Test ZoneListResponse with empty list."""
        data = {
            "items": [],
            "pagination": {"total": 0, "limit": 50, "offset": 0, "has_more": False},
        }
        schema = ZoneListResponse(**data)
        assert schema.items == []
        assert schema.pagination.total == 0


# =============================================================================
# Geometric Validation Tests
# =============================================================================


class TestGeometricValidation:
    """Tests for polygon geometric validation in zone coordinates."""

    def test_valid_rectangle(self) -> None:
        """Test valid rectangle coordinates."""
        data = {
            "name": "Test Zone",
            "coordinates": [[0.1, 0.1], [0.4, 0.1], [0.4, 0.4], [0.1, 0.4]],
        }
        schema = ZoneCreate(**data)
        assert len(schema.coordinates) == 4

    def test_valid_triangle(self) -> None:
        """Test valid triangle coordinates (minimum 3 points)."""
        data = {
            "name": "Triangle Zone",
            "coordinates": [[0.1, 0.1], [0.5, 0.9], [0.9, 0.1]],
        }
        schema = ZoneCreate(**data)
        assert len(schema.coordinates) == 3

    def test_valid_pentagon(self) -> None:
        """Test valid pentagon (5 points)."""
        data = {
            "name": "Pentagon Zone",
            "coordinates": [
                [0.5, 0.1],
                [0.8, 0.4],
                [0.7, 0.8],
                [0.3, 0.8],
                [0.2, 0.4],
            ],
        }
        schema = ZoneCreate(**data)
        assert len(schema.coordinates) == 5

    def test_self_intersecting_bowtie_rejected(self) -> None:
        """Test that self-intersecting bowtie shape is rejected.

        Note: The bowtie shape has near-zero signed area (positive and negative
        regions cancel out), so it may be rejected by either the area check
        or the self-intersection check.
        """
        from pydantic import ValidationError

        # Bowtie shape: edges cross in the middle
        data = {
            "name": "Bowtie Zone",
            "coordinates": [[0.1, 0.1], [0.9, 0.9], [0.9, 0.1], [0.1, 0.9]],
        }
        with pytest.raises(ValidationError):
            ZoneCreate(**data)
        # Shape is invalid - rejected by geometric validation

    def test_self_intersecting_figure_eight_rejected(self) -> None:
        """Test that self-intersecting figure-8 shape is rejected.

        Note: The figure-8 shape has near-zero signed area, so it may be
        rejected by either the area check or the self-intersection check.
        """
        from pydantic import ValidationError

        # Figure-8 shape with crossing edges
        data = {
            "name": "Figure 8 Zone",
            "coordinates": [
                [0.2, 0.2],
                [0.8, 0.2],
                [0.2, 0.8],
                [0.8, 0.8],
            ],
        }
        with pytest.raises(ValidationError):
            ZoneCreate(**data)
        # Shape is invalid - rejected by geometric validation

    def test_self_intersecting_star_rejected(self) -> None:
        """Test that self-intersecting star shape is rejected.

        This is a non-degenerate self-intersecting polygon that has
        positive area but still self-intersects.
        """
        from pydantic import ValidationError

        # 5-pointed star (decagon with self-intersecting edges)
        # Drawing a star by connecting every other vertex
        data = {
            "name": "Star Zone",
            "coordinates": [
                [0.5, 0.1],  # Top
                [0.3, 0.9],  # Bottom left
                [0.9, 0.35],  # Right
                [0.1, 0.35],  # Left
                [0.7, 0.9],  # Bottom right
            ],
        }
        with pytest.raises(ValidationError) as exc_info:
            ZoneCreate(**data)
        assert "self-intersecting" in str(exc_info.value).lower()

    def test_duplicate_consecutive_points_rejected(self) -> None:
        """Test that duplicate consecutive points are rejected."""
        from pydantic import ValidationError

        data = {
            "name": "Duplicate Points Zone",
            "coordinates": [[0.1, 0.1], [0.1, 0.1], [0.5, 0.5], [0.1, 0.5]],
        }
        with pytest.raises(ValidationError) as exc_info:
            ZoneCreate(**data)
        assert "duplicate consecutive points" in str(exc_info.value).lower()

    def test_degenerate_collinear_points_rejected(self) -> None:
        """Test that collinear points (zero area) are rejected."""
        from pydantic import ValidationError

        # All points on a line - zero area polygon
        data = {
            "name": "Collinear Zone",
            "coordinates": [[0.1, 0.1], [0.5, 0.5], [0.9, 0.9]],
        }
        with pytest.raises(ValidationError) as exc_info:
            ZoneCreate(**data)
        assert "zero" in str(exc_info.value).lower() or "area" in str(exc_info.value).lower()

    def test_very_small_area_rejected(self) -> None:
        """Test that extremely small area polygons are rejected.

        Note: Points this close together may also trigger duplicate detection
        due to floating point tolerance, which is also a valid rejection.
        """
        from pydantic import ValidationError

        # Near-zero area triangle (slightly more spread out to avoid duplicate detection)
        data = {
            "name": "Tiny Zone",
            "coordinates": [[0.5, 0.5], [0.50001, 0.5], [0.50001, 0.50001]],
        }
        with pytest.raises(ValidationError) as exc_info:
            ZoneCreate(**data)
        # Should be rejected for zero/near-zero area
        error_msg = str(exc_info.value).lower()
        assert "zero" in error_msg or "area" in error_msg

    def test_coordinates_out_of_range_rejected(self) -> None:
        """Test that coordinates outside 0-1 range are rejected."""
        from pydantic import ValidationError

        data = {
            "name": "Out of Range Zone",
            "coordinates": [[0.1, 0.1], [1.5, 0.1], [1.5, 0.5], [0.1, 0.5]],
        }
        with pytest.raises(ValidationError):
            ZoneCreate(**data)

    def test_negative_coordinates_rejected(self) -> None:
        """Test that negative coordinates are rejected."""
        from pydantic import ValidationError

        data = {
            "name": "Negative Zone",
            "coordinates": [[-0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [-0.1, 0.5]],
        }
        with pytest.raises(ValidationError):
            ZoneCreate(**data)

    def test_fewer_than_3_points_rejected(self) -> None:
        """Test that fewer than 3 points is rejected by min_length."""
        from pydantic import ValidationError

        data = {
            "name": "Too Few Points Zone",
            "coordinates": [[0.1, 0.1], [0.5, 0.5]],
        }
        with pytest.raises(ValidationError):
            ZoneCreate(**data)

    def test_wrong_point_format_rejected(self) -> None:
        """Test that wrong point format (not [x, y]) is rejected."""
        from pydantic import ValidationError

        data = {
            "name": "Wrong Format Zone",
            "coordinates": [[0.1, 0.1, 0.1], [0.5, 0.1], [0.5, 0.5]],
        }
        with pytest.raises(ValidationError):
            ZoneCreate(**data)

    def test_valid_concave_polygon(self) -> None:
        """Test valid concave (non-convex) polygon is accepted."""
        # L-shaped polygon (concave but valid)
        data = {
            "name": "L-Shape Zone",
            "coordinates": [
                [0.1, 0.1],
                [0.5, 0.1],
                [0.5, 0.5],
                [0.3, 0.5],
                [0.3, 0.9],
                [0.1, 0.9],
            ],
        }
        schema = ZoneCreate(**data)
        assert len(schema.coordinates) == 6

    def test_update_schema_validates_coordinates(self) -> None:
        """Test that ZoneUpdate also validates coordinates.

        Uses a 5-pointed star shape which is self-intersecting but has
        positive area, ensuring the self-intersection check is triggered.
        """
        from pydantic import ValidationError

        # 5-pointed star (self-intersecting)
        data = {
            "coordinates": [
                [0.5, 0.1],  # Top
                [0.3, 0.9],  # Bottom left
                [0.9, 0.35],  # Right
                [0.1, 0.35],  # Left
                [0.7, 0.9],  # Bottom right
            ],
        }
        with pytest.raises(ValidationError) as exc_info:
            ZoneUpdate(**data)
        assert "self-intersecting" in str(exc_info.value).lower()

    def test_update_schema_allows_none_coordinates(self) -> None:
        """Test that ZoneUpdate allows None for coordinates (partial update)."""
        data = {"name": "New Name"}
        schema = ZoneUpdate(**data)
        assert schema.coordinates is None

    def test_complex_valid_polygon(self) -> None:
        """Test complex but valid polygon with many points."""
        data = {
            "name": "Complex Zone",
            "coordinates": [
                [0.1, 0.5],
                [0.3, 0.2],
                [0.5, 0.1],
                [0.7, 0.2],
                [0.9, 0.5],
                [0.7, 0.8],
                [0.5, 0.9],
                [0.3, 0.8],
            ],
        }
        schema = ZoneCreate(**data)
        assert len(schema.coordinates) == 8

    def test_clockwise_and_counterclockwise_valid(self) -> None:
        """Test that both clockwise and counter-clockwise polygons are valid."""
        # Counter-clockwise rectangle
        ccw_data = {
            "name": "CCW Zone",
            "coordinates": [[0.1, 0.1], [0.4, 0.1], [0.4, 0.4], [0.1, 0.4]],
        }
        ccw_schema = ZoneCreate(**ccw_data)
        assert len(ccw_schema.coordinates) == 4

        # Clockwise rectangle (reverse order)
        cw_data = {
            "name": "CW Zone",
            "coordinates": [[0.1, 0.1], [0.1, 0.4], [0.4, 0.4], [0.4, 0.1]],
        }
        cw_schema = ZoneCreate(**cw_data)
        assert len(cw_schema.coordinates) == 4


class TestGeometricHelperFunctions:
    """Tests for internal geometric helper functions."""

    def test_polygon_area_positive_for_ccw(self) -> None:
        """Test that shoelace formula gives positive area for CCW polygon."""
        from backend.api.schemas.zone import _polygon_area

        # Counter-clockwise unit square
        coords = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
        area = _polygon_area(coords)
        assert area > 0
        assert abs(area - 1.0) < 1e-9

    def test_polygon_area_negative_for_cw(self) -> None:
        """Test that shoelace formula gives negative area for CW polygon."""
        from backend.api.schemas.zone import _polygon_area

        # Clockwise unit square
        coords = [[0.0, 0.0], [0.0, 1.0], [1.0, 1.0], [1.0, 0.0]]
        area = _polygon_area(coords)
        assert area < 0
        assert abs(area + 1.0) < 1e-9

    def test_polygon_area_triangle(self) -> None:
        """Test area calculation for triangle."""
        from backend.api.schemas.zone import _polygon_area

        # Right triangle with base 0.5 and height 0.5 -> area = 0.125
        coords = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5]]
        area = abs(_polygon_area(coords))
        assert abs(area - 0.125) < 1e-9

    def test_is_self_intersecting_simple_polygon(self) -> None:
        """Test that simple polygon is not self-intersecting."""
        from backend.api.schemas.zone import _is_self_intersecting

        coords = [[0.1, 0.1], [0.4, 0.1], [0.4, 0.4], [0.1, 0.4]]
        assert _is_self_intersecting(coords) is False

    def test_is_self_intersecting_bowtie(self) -> None:
        """Test that bowtie is self-intersecting."""
        from backend.api.schemas.zone import _is_self_intersecting

        coords = [[0.1, 0.1], [0.9, 0.9], [0.9, 0.1], [0.1, 0.9]]
        assert _is_self_intersecting(coords) is True

    def test_is_self_intersecting_triangle(self) -> None:
        """Test that triangle cannot be self-intersecting."""
        from backend.api.schemas.zone import _is_self_intersecting

        coords = [[0.1, 0.1], [0.5, 0.9], [0.9, 0.1]]
        assert _is_self_intersecting(coords) is False

    def test_has_duplicate_consecutive_points_true(self) -> None:
        """Test detection of duplicate consecutive points."""
        from backend.api.schemas.zone import _has_duplicate_consecutive_points

        coords = [[0.1, 0.1], [0.1, 0.1], [0.5, 0.5], [0.1, 0.5]]
        assert _has_duplicate_consecutive_points(coords) is True

    def test_has_duplicate_consecutive_points_false(self) -> None:
        """Test no false positive for distinct points."""
        from backend.api.schemas.zone import _has_duplicate_consecutive_points

        coords = [[0.1, 0.1], [0.4, 0.1], [0.4, 0.4], [0.1, 0.4]]
        assert _has_duplicate_consecutive_points(coords) is False

    def test_has_duplicate_consecutive_points_wrap_around(self) -> None:
        """Test duplicate detection wraps around from last to first point."""
        from backend.api.schemas.zone import _has_duplicate_consecutive_points

        # Last point equals first point
        coords = [[0.1, 0.1], [0.4, 0.1], [0.4, 0.4], [0.1, 0.1]]
        assert _has_duplicate_consecutive_points(coords) is True

    def test_validate_polygon_geometry_valid(self) -> None:
        """Test full validation passes for valid polygon."""
        from backend.api.schemas.zone import _validate_polygon_geometry

        coords = [[0.1, 0.1], [0.4, 0.1], [0.4, 0.4], [0.1, 0.4]]
        result = _validate_polygon_geometry(coords)
        assert result == coords

    def test_validate_polygon_geometry_self_intersecting(self) -> None:
        """Test validation fails for self-intersecting polygon.

        Uses a 5-pointed star which has positive area but self-intersects.
        """
        from backend.api.schemas.zone import _validate_polygon_geometry

        # 5-pointed star (self-intersecting but positive area)
        coords = [
            [0.5, 0.1],  # Top
            [0.3, 0.9],  # Bottom left
            [0.9, 0.35],  # Right
            [0.1, 0.35],  # Left
            [0.7, 0.9],  # Bottom right
        ]
        with pytest.raises(ValueError, match="self-intersecting"):
            _validate_polygon_geometry(coords)

    def test_validate_polygon_geometry_degenerate(self) -> None:
        """Test validation fails for degenerate polygon."""
        from backend.api.schemas.zone import _validate_polygon_geometry

        # Collinear points
        coords = [[0.1, 0.1], [0.5, 0.5], [0.9, 0.9]]
        with pytest.raises(ValueError, match="zero"):
            _validate_polygon_geometry(coords)

    def test_validate_polygon_geometry_out_of_range(self) -> None:
        """Test validation fails for coordinates out of range."""
        from backend.api.schemas.zone import _validate_polygon_geometry

        coords = [[0.1, 0.1], [1.5, 0.1], [1.5, 0.5], [0.1, 0.5]]
        with pytest.raises(ValueError, match="normalized"):
            _validate_polygon_geometry(coords)
