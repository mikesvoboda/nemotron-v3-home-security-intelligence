"""Unit tests for admin API routes.

Tests cover:
- POST /api/admin/seed/cameras - Seed test cameras
- POST /api/admin/seed/events - Seed test events
- DELETE /api/admin/seed/clear - Clear all seeded data
- Security: Defense-in-depth access control
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.api.routes.admin import (
    ClearDataRequest,
    ClearDataResponse,
    SeedCamerasRequest,
    SeedCamerasResponse,
    SeedEventsRequest,
    SeedEventsResponse,
    require_admin_access,
    router,
)
from backend.core.database import get_db
from backend.models.camera import Camera

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_settings():
    """Create mock settings with admin access enabled."""
    settings = MagicMock()
    settings.debug = True
    settings.admin_enabled = True
    settings.admin_api_key = None
    return settings


@pytest.fixture
def mock_settings_debug_disabled():
    """Create mock settings with debug disabled."""
    settings = MagicMock()
    settings.debug = False
    settings.admin_enabled = True
    settings.admin_api_key = None
    return settings


@pytest.fixture
def mock_settings_admin_disabled():
    """Create mock settings with admin disabled."""
    settings = MagicMock()
    settings.debug = True
    settings.admin_enabled = False
    settings.admin_api_key = None
    return settings


@pytest.fixture
def mock_settings_with_api_key():
    """Create mock settings with API key required."""
    settings = MagicMock()
    settings.debug = True
    settings.admin_enabled = True
    settings.admin_api_key = "test-admin-key-12345"
    return settings


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock database session.

    This fixture properly simulates flush() by assigning auto-incrementing IDs
    to Detection and Event objects that were added via add().
    """
    session = AsyncMock()

    # Track added objects for ID assignment on flush
    added_objects: list = []
    id_counter = {"value": 1}

    def mock_add(obj):
        added_objects.append(obj)

    async def mock_flush():
        # Assign IDs to objects that don't have them yet
        for obj in added_objects:
            if hasattr(obj, "id") and obj.id is None:
                obj.id = id_counter["value"]
                id_counter["value"] += 1

    session.add = MagicMock(side_effect=mock_add)
    session.commit = AsyncMock()
    session.flush = AsyncMock(side_effect=mock_flush)
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def client(mock_db_session: AsyncMock, mock_settings) -> TestClient:
    """Create a test client with mocked dependencies."""
    app = FastAPI()
    app.include_router(router)

    async def override_get_db():
        yield mock_db_session

    app.dependency_overrides[get_db] = override_get_db

    with (
        patch("backend.api.routes.admin.get_settings", return_value=mock_settings),
        TestClient(app) as test_client,
    ):
        yield test_client


@pytest.fixture
def sample_camera() -> Camera:
    """Create a sample camera object for testing."""
    return Camera(
        id="front-door",
        name="Front Door",
        folder_path="/export/foscam/front_door",
        status="online",
        created_at=datetime(2025, 12, 23, 10, 0, 0),
        last_seen_at=None,
    )


# =============================================================================
# require_admin_access Tests
# =============================================================================


class TestRequireAdminAccess:
    """Tests for the require_admin_access security function."""

    def test_admin_access_allowed_when_debug_and_admin_enabled(self, mock_settings) -> None:
        """Test that admin access is allowed when both debug and admin_enabled are True."""
        with patch("backend.api.routes.admin.get_settings", return_value=mock_settings):
            # Should not raise
            require_admin_access()

    def test_admin_access_denied_when_debug_disabled(self, mock_settings_debug_disabled) -> None:
        """Test that admin access is denied when debug is False."""
        with patch(
            "backend.api.routes.admin.get_settings",
            return_value=mock_settings_debug_disabled,
        ):
            with pytest.raises(HTTPException) as exc_info:
                require_admin_access()
            assert exc_info.value.status_code == 403
            assert "DEBUG=true" in exc_info.value.detail

    def test_admin_access_denied_when_admin_disabled(self, mock_settings_admin_disabled) -> None:
        """Test that admin access is denied when admin_enabled is False."""
        with patch(
            "backend.api.routes.admin.get_settings",
            return_value=mock_settings_admin_disabled,
        ):
            with pytest.raises(HTTPException) as exc_info:
                require_admin_access()
            assert exc_info.value.status_code == 403
            assert "ADMIN_ENABLED=true" in exc_info.value.detail

    def test_admin_access_denied_without_api_key_when_required(
        self, mock_settings_with_api_key
    ) -> None:
        """Test that admin access is denied when API key is required but not provided."""
        with patch(
            "backend.api.routes.admin.get_settings",
            return_value=mock_settings_with_api_key,
        ):
            with pytest.raises(HTTPException) as exc_info:
                require_admin_access(x_admin_api_key=None)
            assert exc_info.value.status_code == 401
            assert "Admin API key required" in exc_info.value.detail

    def test_admin_access_denied_with_invalid_api_key(self, mock_settings_with_api_key) -> None:
        """Test that admin access is denied when API key is invalid."""
        with patch(
            "backend.api.routes.admin.get_settings",
            return_value=mock_settings_with_api_key,
        ):
            with pytest.raises(HTTPException) as exc_info:
                require_admin_access(x_admin_api_key="wrong-key")
            assert exc_info.value.status_code == 401
            assert "Invalid admin API key" in exc_info.value.detail

    def test_admin_access_allowed_with_valid_api_key(self, mock_settings_with_api_key) -> None:
        """Test that admin access is allowed when API key is valid."""
        with patch(
            "backend.api.routes.admin.get_settings",
            return_value=mock_settings_with_api_key,
        ):
            # Should not raise
            require_admin_access(x_admin_api_key="test-admin-key-12345")


# =============================================================================
# Seed Cameras Tests
# =============================================================================


class TestSeedCameras:
    """Tests for POST /api/admin/seed/cameras endpoint."""

    def test_seed_cameras_default_count(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test seeding cameras with default count."""
        # Mock empty existing cameras
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        response = client.post("/api/admin/seed/cameras", json={})

        assert response.status_code == 201
        data = response.json()
        assert "created" in data
        assert "cleared" in data
        assert "cameras" in data

    def test_seed_cameras_with_count(self, client: TestClient, mock_db_session: AsyncMock) -> None:
        """Test seeding cameras with specific count."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        response = client.post("/api/admin/seed/cameras", json={"count": 3})

        assert response.status_code == 201
        data = response.json()
        assert data["created"] == 3

    def test_seed_cameras_clear_existing(
        self, client: TestClient, mock_db_session: AsyncMock, sample_camera: Camera
    ) -> None:
        """Test seeding cameras with clear_existing flag."""
        # Mock existing cameras for counting
        mock_count_result = MagicMock()
        mock_count_result.scalars.return_value.all.return_value = [sample_camera]

        # Mock no existing camera when checking individually
        mock_check_result = MagicMock()
        mock_check_result.scalar_one_or_none.return_value = None

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # First call is to get existing cameras
                return mock_count_result
            return mock_check_result

        mock_db_session.execute = AsyncMock(side_effect=side_effect)

        response = client.post("/api/admin/seed/cameras", json={"count": 2, "clear_existing": True})

        assert response.status_code == 201
        data = response.json()
        assert data["cleared"] == 1

    def test_seed_cameras_skip_existing(
        self, client: TestClient, mock_db_session: AsyncMock, sample_camera: Camera
    ) -> None:
        """Test that existing cameras are skipped."""
        # Mock the batch query for existing camera IDs
        # New code uses: select(Camera.id).where(Camera.id.in_(...))
        # which returns rows of (camera_id,) tuples
        mock_result = MagicMock()
        # Return the sample camera's ID as a tuple row (batch load pattern)
        mock_result.all.return_value = [(sample_camera.id,)]
        mock_db_session.execute.return_value = mock_result

        response = client.post("/api/admin/seed/cameras", json={"count": 1})

        assert response.status_code == 201
        data = response.json()
        # Should create 0 since the camera already exists
        assert data["created"] == 0

    def test_seed_cameras_invalid_count_too_high(self, client: TestClient) -> None:
        """Test seeding cameras with count exceeding maximum."""
        response = client.post("/api/admin/seed/cameras", json={"count": 10})

        assert response.status_code == 422  # Validation error

    def test_seed_cameras_invalid_count_zero(self, client: TestClient) -> None:
        """Test seeding cameras with count of zero."""
        response = client.post("/api/admin/seed/cameras", json={"count": 0})

        assert response.status_code == 422  # Validation error


# =============================================================================
# Seed Events Tests
# =============================================================================


class TestSeedEvents:
    """Tests for POST /api/admin/seed/events endpoint."""

    def test_seed_events_no_cameras_returns_error(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test seeding events fails when no cameras exist."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        response = client.post("/api/admin/seed/events", json={})

        assert response.status_code == 400
        data = response.json()
        assert "cameras" in data["detail"].lower()

    def test_seed_events_with_cameras(
        self, client: TestClient, mock_db_session: AsyncMock, sample_camera: Camera
    ) -> None:
        """Test seeding events when cameras exist."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_camera]
        mock_db_session.execute.return_value = mock_result

        response = client.post("/api/admin/seed/events", json={"count": 5})

        assert response.status_code == 201
        data = response.json()
        assert data["events_created"] == 5
        assert "detections_created" in data

    def test_seed_events_default_count(
        self, client: TestClient, mock_db_session: AsyncMock, sample_camera: Camera
    ) -> None:
        """Test seeding events with default count."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_camera]
        mock_db_session.execute.return_value = mock_result

        response = client.post("/api/admin/seed/events", json={})

        assert response.status_code == 201
        data = response.json()
        assert data["events_created"] == 15  # Default count

    def test_seed_events_invalid_count_too_high(self, client: TestClient) -> None:
        """Test seeding events with count exceeding maximum."""
        response = client.post("/api/admin/seed/events", json={"count": 200})

        assert response.status_code == 422  # Validation error

    def test_seed_events_invalid_count_zero(self, client: TestClient) -> None:
        """Test seeding events with count of zero."""
        response = client.post("/api/admin/seed/events", json={"count": 0})

        assert response.status_code == 422  # Validation error


# =============================================================================
# Clear Data Tests
# =============================================================================


class TestClearData:
    """Tests for DELETE /api/admin/seed/clear endpoint."""

    def test_clear_data_requires_confirmation(self, client: TestClient) -> None:
        """Test clearing data requires correct confirmation string."""
        response = client.request(
            "DELETE", "/api/admin/seed/clear", json={"confirm": "wrong_string"}
        )

        assert response.status_code == 400
        data = response.json()
        assert "DELETE_ALL_DATA" in data["detail"]

    def test_clear_data_success(self, client: TestClient, mock_db_session: AsyncMock) -> None:
        """Test clearing data with correct confirmation."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        with patch("backend.api.routes.admin.get_db_audit_service") as mock_get_audit:
            mock_audit = MagicMock()
            mock_audit.log_action = AsyncMock()
            mock_get_audit.return_value = mock_audit
            response = client.request(
                "DELETE",
                "/api/admin/seed/clear",
                json={"confirm": "DELETE_ALL_DATA"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "cameras_cleared" in data
        assert "events_cleared" in data
        assert "detections_cleared" in data


# =============================================================================
# Schema Tests
# =============================================================================


class TestSeedCamerasRequestSchema:
    """Tests for SeedCamerasRequest schema validation."""

    def test_seed_cameras_request_defaults(self) -> None:
        """Test SeedCamerasRequest default values."""
        schema = SeedCamerasRequest()
        assert schema.count == 6
        assert schema.clear_existing is False
        assert schema.create_folders is False

    def test_seed_cameras_request_custom_values(self) -> None:
        """Test SeedCamerasRequest with custom values."""
        schema = SeedCamerasRequest(count=3, clear_existing=True, create_folders=True)
        assert schema.count == 3
        assert schema.clear_existing is True
        assert schema.create_folders is True

    def test_seed_cameras_request_count_validation_min(self) -> None:
        """Test SeedCamerasRequest count minimum validation."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SeedCamerasRequest(count=0)

    def test_seed_cameras_request_count_validation_max(self) -> None:
        """Test SeedCamerasRequest count maximum validation."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SeedCamerasRequest(count=7)


class TestSeedCamerasResponseSchema:
    """Tests for SeedCamerasResponse schema validation."""

    def test_seed_cameras_response_valid(self) -> None:
        """Test SeedCamerasResponse with valid data."""
        schema = SeedCamerasResponse(
            created=3,
            cleared=0,
            cameras=[{"id": "test", "name": "Test Camera"}],
        )
        assert schema.created == 3
        assert schema.cleared == 0
        assert len(schema.cameras) == 1


class TestSeedEventsRequestSchema:
    """Tests for SeedEventsRequest schema validation."""

    def test_seed_events_request_defaults(self) -> None:
        """Test SeedEventsRequest default values."""
        schema = SeedEventsRequest()
        assert schema.count == 15
        assert schema.clear_existing is False

    def test_seed_events_request_custom_values(self) -> None:
        """Test SeedEventsRequest with custom values."""
        schema = SeedEventsRequest(count=50, clear_existing=True)
        assert schema.count == 50
        assert schema.clear_existing is True

    def test_seed_events_request_count_validation_min(self) -> None:
        """Test SeedEventsRequest count minimum validation."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SeedEventsRequest(count=0)

    def test_seed_events_request_count_validation_max(self) -> None:
        """Test SeedEventsRequest count maximum validation."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SeedEventsRequest(count=101)


class TestSeedEventsResponseSchema:
    """Tests for SeedEventsResponse schema validation."""

    def test_seed_events_response_valid(self) -> None:
        """Test SeedEventsResponse with valid data."""
        schema = SeedEventsResponse(
            events_created=10,
            detections_created=25,
            events_cleared=0,
            detections_cleared=0,
        )
        assert schema.events_created == 10
        assert schema.detections_created == 25


class TestClearDataRequestSchema:
    """Tests for ClearDataRequest schema validation."""

    def test_clear_data_request_valid(self) -> None:
        """Test ClearDataRequest with valid confirmation."""
        schema = ClearDataRequest(confirm="DELETE_ALL_DATA")
        assert schema.confirm == "DELETE_ALL_DATA"

    def test_clear_data_request_requires_confirm(self) -> None:
        """Test ClearDataRequest requires confirm field."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ClearDataRequest()


class TestClearDataResponseSchema:
    """Tests for ClearDataResponse schema validation."""

    def test_clear_data_response_valid(self) -> None:
        """Test ClearDataResponse with valid data."""
        schema = ClearDataResponse(
            cameras_cleared=6,
            events_cleared=15,
            detections_cleared=50,
        )
        assert schema.cameras_cleared == 6
        assert schema.events_cleared == 15
        assert schema.detections_cleared == 50


# =============================================================================
# API Key Security Tests
# =============================================================================


class TestAdminAPIKeySecurity:
    """Tests for admin API key security."""

    def test_api_key_uses_constant_time_comparison(self, mock_settings_with_api_key) -> None:
        """Test that API key validation uses secrets.compare_digest."""
        with (
            patch(
                "backend.api.routes.admin.get_settings",
                return_value=mock_settings_with_api_key,
            ),
            patch("backend.api.routes.admin.secrets.compare_digest") as mock_compare,
        ):
            mock_compare.return_value = True
            require_admin_access(x_admin_api_key="test-admin-key-12345")
            mock_compare.assert_called_once()

    def test_api_key_header_name(self, mock_settings_with_api_key) -> None:
        """Test that the API key header is X-Admin-API-Key."""
        with patch(
            "backend.api.routes.admin.get_settings",
            return_value=mock_settings_with_api_key,
        ):
            with pytest.raises(HTTPException) as exc_info:
                require_admin_access(x_admin_api_key=None)
            assert "X-Admin-API-Key" in exc_info.value.detail
