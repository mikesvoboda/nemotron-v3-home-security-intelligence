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
from fastapi import FastAPI
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
    """Tests for the require_admin_access function.

    SECURITY: Admin endpoints are controlled by the ADMIN_ENABLED setting.
    Network binding to 127.0.0.1 is the primary security boundary for
    single-user local deployments.
    """

    def test_admin_access_allowed_when_admin_enabled(self) -> None:
        """Test that admin access is allowed when admin_enabled=True."""
        from unittest.mock import patch

        with patch("backend.api.routes.admin.get_settings") as mock_settings:
            mock_settings.return_value.admin_enabled = True
            # Should not raise
            require_admin_access()

    def test_admin_access_blocked_when_admin_disabled(self) -> None:
        """Test that admin access is blocked when admin_enabled=False."""
        from unittest.mock import patch

        from fastapi import HTTPException

        with patch("backend.api.routes.admin.get_settings") as mock_settings:
            mock_settings.return_value.admin_enabled = False
            with pytest.raises(HTTPException) as exc_info:
                require_admin_access()
            assert exc_info.value.status_code == 403
            assert "ADMIN_ENABLED=true" in exc_info.value.detail

    def test_admin_access_independent_of_debug_flag(self) -> None:
        """Test that admin access only depends on admin_enabled, not debug."""
        from unittest.mock import patch

        # Admin enabled with debug=False should still work
        with patch("backend.api.routes.admin.get_settings") as mock_settings:
            mock_settings.return_value.admin_enabled = True
            mock_settings.return_value.debug = False
            # Should not raise - admin_enabled is the only check
            result = require_admin_access()
            assert result is None

    def test_admin_blocked_regardless_of_debug_flag(self) -> None:
        """Test that admin is blocked when disabled, regardless of debug setting."""
        from unittest.mock import patch

        from fastapi import HTTPException

        with patch("backend.api.routes.admin.get_settings") as mock_settings:
            mock_settings.return_value.admin_enabled = False
            mock_settings.return_value.debug = True  # debug=True should not override
            with pytest.raises(HTTPException) as exc_info:
                require_admin_access()
            assert exc_info.value.status_code == 403
            assert "ADMIN_ENABLED=true" in exc_info.value.detail


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
# User Management Tests (Phase 2: API Protection)
# =============================================================================


class TestAdminUserManagement:
    """Tests for admin user management endpoints.

    These tests cover the Phase 2 API Protection requirements where admins
    can create additional users after initial setup.
    """

    @pytest.fixture
    def mock_admin_user(self) -> MagicMock:
        """Create a mock admin user."""
        user = MagicMock()
        user.id = "admin-user-123"
        user.username = "admin"
        user.email = "admin@example.com"
        user.is_admin = True
        user.is_active = True
        user.created_at = datetime(2025, 12, 23, 10, 0, 0)
        user.last_login_at = None
        return user

    @pytest.fixture
    def mock_regular_user(self) -> MagicMock:
        """Create a mock regular (non-admin) user."""
        user = MagicMock()
        user.id = "regular-user-456"
        user.username = "regularuser"
        user.email = "user@example.com"
        user.is_admin = False
        user.is_active = True
        user.created_at = datetime(2025, 12, 23, 10, 0, 0)
        user.last_login_at = None
        return user

    @pytest.fixture
    def admin_client(
        self, mock_db_session: AsyncMock, mock_settings, mock_admin_user: MagicMock
    ) -> TestClient:
        """Create a test client authenticated as an admin user."""
        from backend.api.routes.auth import get_current_admin_user, get_current_user

        app = FastAPI()
        app.include_router(router)

        async def override_get_db():
            yield mock_db_session

        async def override_get_current_user():
            return mock_admin_user

        async def override_get_current_admin_user():
            return mock_admin_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_current_admin_user] = override_get_current_admin_user

        with (
            patch("backend.api.routes.admin.get_settings", return_value=mock_settings),
            TestClient(app) as test_client,
        ):
            yield test_client

    @pytest.fixture
    def non_admin_client(
        self, mock_db_session: AsyncMock, mock_settings, mock_regular_user: MagicMock
    ) -> TestClient:
        """Create a test client authenticated as a non-admin user."""
        from fastapi import HTTPException, status

        from backend.api.routes.auth import get_current_admin_user, get_current_user

        app = FastAPI()
        app.include_router(router)

        async def override_get_db():
            yield mock_db_session

        async def override_get_current_user():
            return mock_regular_user

        async def override_get_current_admin_user():
            # Non-admin users should get 403 when accessing admin endpoints
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required",
            )

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_current_admin_user] = override_get_current_admin_user

        with (
            patch("backend.api.routes.admin.get_settings", return_value=mock_settings),
            TestClient(app) as test_client,
        ):
            yield test_client

    def test_create_user_requires_admin(
        self, non_admin_client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that creating users requires admin privileges."""
        user_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "SecurePassword123!",  # pragma: allowlist secret
            "is_admin": False,
        }

        response = non_admin_client.post("/api/admin/users", json=user_data)

        assert response.status_code == 403
        data = response.json()
        assert "admin" in data["detail"].lower()

    def test_create_user_non_admin_forbidden(
        self, non_admin_client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that non-admin users cannot create users."""
        user_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "SecurePassword123!",  # pragma: allowlist secret
        }

        response = non_admin_client.post("/api/admin/users", json=user_data)

        assert response.status_code == 403

    def test_create_user_creates_non_admin_by_default(
        self, admin_client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that newly created users are non-admin by default."""
        user_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "SecurePassword123!",  # pragma: allowlist secret
        }

        # Mock no existing users with same username/email
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        response = admin_client.post("/api/admin/users", json=user_data)

        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "newuser"
        assert data["is_admin"] is False

    def test_list_users_requires_admin(
        self, non_admin_client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that listing users requires admin privileges."""
        response = non_admin_client.get("/api/admin/users")

        assert response.status_code == 403

    def test_delete_user_requires_admin(
        self, non_admin_client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that deleting users requires admin privileges."""
        response = non_admin_client.delete("/api/admin/users/user123")

        assert response.status_code == 403

    def test_admin_cannot_delete_self(
        self,
        mock_db_session: AsyncMock,
        mock_settings,
    ) -> None:
        """Test that admins cannot delete their own account."""
        from backend.api.routes.auth import get_current_admin_user, get_current_user

        # Create admin user with specific ID
        admin_user = MagicMock()
        admin_user.id = "admin-self-delete-test-id"
        admin_user.username = "admin"
        admin_user.email = "admin@example.com"
        admin_user.is_admin = True
        admin_user.is_active = True
        admin_user.created_at = datetime(2025, 12, 23, 10, 0, 0)
        admin_user.last_login_at = None

        app = FastAPI()
        app.include_router(router)

        async def override_get_db():
            yield mock_db_session

        async def override_get_current_user():
            return admin_user

        async def override_get_current_admin_user():
            return admin_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_current_admin_user] = override_get_current_admin_user

        with (
            patch("backend.api.routes.admin.get_settings", return_value=mock_settings),
            TestClient(app) as test_client,
        ):
            # Try to delete self (using the admin's own ID)
            response = test_client.delete(f"/api/admin/users/{admin_user.id}")

        assert response.status_code == 400
        data = response.json()
        assert "cannot delete" in data["detail"].lower() or "your own" in data["detail"].lower()
