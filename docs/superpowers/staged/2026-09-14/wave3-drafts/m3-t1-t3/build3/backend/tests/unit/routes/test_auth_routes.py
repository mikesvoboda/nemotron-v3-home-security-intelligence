"""Unit tests for authentication API routes.

Tests cover the authentication endpoints including:
- Setup status checking
- User registration (first user becomes admin)
- User login with JWT tokens
- User logout
- Current user retrieval

These tests MUST FAIL initially (RED phase of TDD) as the endpoints
and services don't exist yet.

Test Coverage:
- POST /api/auth/register - User registration
- POST /api/auth/login - User authentication
- POST /api/auth/logout - Session termination
- GET /api/auth/me - Current user info
- GET /api/auth/setup-status - Setup completion check
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

# These imports WILL FAIL initially - that's the point of TDD
try:
    from backend.api.routes.auth import router as auth_router
    from backend.api.schemas.auth import (
        LoginRequest,
        LoginResponse,
        RegisterRequest,
        SetupStatusResponse,
        UserResponse,
    )
except ImportError:
    # Placeholders for test structure
    auth_router = None

    class RegisterRequest:
        pass

    class LoginRequest:
        pass

    class LoginResponse:
        pass

    class UserResponse:
        pass

    class SetupStatusResponse:
        pass


# Mark as unit tests
pytestmark = pytest.mark.unit


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
    session.execute = AsyncMock()
    return session


@pytest.fixture
def mock_auth_service() -> MagicMock:
    """Create a mock authentication service."""
    service = MagicMock()
    service.register_user = AsyncMock()
    service.authenticate_user = AsyncMock()
    service.create_access_token = MagicMock()
    service.create_refresh_token = MagicMock()
    service.verify_token = MagicMock()
    service.hash_password = MagicMock()
    service.verify_password = MagicMock()
    return service


@pytest.fixture
def client(mock_db_session: AsyncMock, mock_auth_service: MagicMock) -> TestClient:
    """Create a test client with mocked dependencies."""
    if auth_router is None:
        pytest.skip("Auth router not implemented yet (expected in TDD RED phase)")

    app = FastAPI()
    app.include_router(auth_router)

    async def override_get_db():
        yield mock_db_session

    from backend.core.database import get_db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client


# =============================================================================
# Setup Status Tests
# =============================================================================


class TestSetupStatus:
    """Tests for GET /api/auth/setup-status endpoint."""

    def test_setup_status_returns_true_when_no_users(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that setup-status returns needs_setup=true when no users exist."""
        # Mock no users
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        response = client.get("/api/auth/setup-status")

        assert response.status_code == 200
        data = response.json()
        assert data["needs_setup"] is True

    def test_setup_status_returns_false_when_users_exist(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that setup-status returns needs_setup=false when users exist."""
        # Mock existing user
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 1  # User count
        mock_db_session.execute.return_value = mock_result

        response = client.get("/api/auth/setup-status")

        assert response.status_code == 200
        data = response.json()
        assert data["needs_setup"] is False

    def test_setup_status_no_auth_required(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that setup-status endpoint doesn't require authentication."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        # No auth headers
        response = client.get("/api/auth/setup-status")

        # Should succeed without authentication
        assert response.status_code == 200


# =============================================================================
# Registration Tests
# =============================================================================


class TestUserRegistration:
    """Tests for POST /api/auth/register endpoint."""

    def test_register_creates_first_user_as_admin(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that first registered user becomes admin."""
        # Mock no existing users
        mock_count_result = MagicMock()
        mock_count_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_count_result

        registration_data = {
            "username": "admin",
            "email": "admin@example.com",
            "password": "SecurePassword123!",  # pragma: allowlist secret
        }

        response = client.post("/api/auth/register", json=registration_data)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["username"] == "admin"
        assert data["email"] == "admin@example.com"
        assert data["is_admin"] is True
        # Password should NOT be in response
        assert "password" not in data
        assert "password_hash" not in data

    def test_register_returns_403_when_users_exist(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that registration is disabled after first user exists."""
        # Mock existing users
        mock_count_result = MagicMock()
        mock_count_result.scalar_one_or_none.return_value = 1
        mock_db_session.execute.return_value = mock_count_result

        registration_data = {
            "username": "hacker",
            "email": "hacker@example.com",
            "password": "Password123!",  # pragma: allowlist secret
        }

        response = client.post("/api/auth/register", json=registration_data)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        data = response.json()
        assert "detail" in data
        assert "registration" in data["detail"].lower()
        assert "disabled" in data["detail"].lower()

    def test_register_validates_password_strength(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that weak passwords are rejected."""
        mock_count_result = MagicMock()
        mock_count_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_count_result

        weak_passwords = [
            "short",  # Too short
            "alllowercase123",  # No uppercase
            "ALLUPPERCASE123",  # No lowercase
            "NoNumbers!",  # No numbers
            "NoSpecial123",  # No special characters
        ]

        for weak_password in weak_passwords:
            registration_data = {
                "username": "testuser",
                "email": "test@example.com",
                "password": weak_password,  # pragma: allowlist secret
            }

            response = client.post("/api/auth/register", json=registration_data)

            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_register_validates_email_format(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that invalid email formats are rejected."""
        mock_count_result = MagicMock()
        mock_count_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_count_result

        invalid_emails = [
            "not_an_email",
            "missing@domain",
            "@nodomain.com",
            "no@domain@double.com",
            "",
        ]

        for invalid_email in invalid_emails:
            registration_data = {
                "username": "testuser",
                "email": invalid_email,
                "password": "SecurePassword123!",  # pragma: allowlist secret
            }

            response = client.post("/api/auth/register", json=registration_data)

            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_register_rejects_duplicate_username(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that duplicate usernames are rejected."""
        # Mock no users initially
        mock_count_result = MagicMock()
        mock_count_result.scalar_one_or_none.return_value = None

        # Mock existing user with same username
        mock_user_result = MagicMock()

        def execute_side_effect(query):
            # Count query returns 0, user lookup returns existing user
            if hasattr(query, "whereclause"):
                mock_user_result.scalar_one_or_none.return_value = MagicMock(username="duplicate")
                return mock_user_result
            return mock_count_result

        mock_db_session.execute.side_effect = execute_side_effect

        registration_data = {
            "username": "duplicate",
            "email": "unique@example.com",
            "password": "SecurePassword123!",  # pragma: allowlist secret
        }

        response = client.post("/api/auth/register", json=registration_data)

        assert response.status_code == status.HTTP_409_CONFLICT
        data = response.json()
        assert "username" in data["detail"].lower()

    def test_register_rejects_duplicate_email(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that duplicate emails are rejected."""
        # Mock no users initially
        mock_count_result = MagicMock()
        mock_count_result.scalar_one_or_none.return_value = None

        # Mock existing user with same email
        mock_user_result = MagicMock()

        def execute_side_effect(query):
            # Count query returns 0, user lookup returns existing user
            if hasattr(query, "whereclause"):
                mock_user_result.scalar_one_or_none.return_value = MagicMock(
                    email="duplicate@example.com"
                )
                return mock_user_result
            return mock_count_result

        mock_db_session.execute.side_effect = execute_side_effect

        registration_data = {
            "username": "uniqueuser",
            "email": "duplicate@example.com",
            "password": "SecurePassword123!",  # pragma: allowlist secret
        }

        response = client.post("/api/auth/register", json=registration_data)

        assert response.status_code == status.HTTP_409_CONFLICT
        data = response.json()
        assert "email" in data["detail"].lower()

    def test_register_validates_required_fields(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that all required fields are validated."""
        # Missing username
        response1 = client.post(
            "/api/auth/register",
            json={
                "email": "test@example.com",
                "password": "SecurePassword123!",  # pragma: allowlist secret
            },
        )
        assert response1.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Missing email
        response2 = client.post(
            "/api/auth/register",
            json={
                "username": "testuser",
                "password": "SecurePassword123!",  # pragma: allowlist secret
            },
        )
        assert response2.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Missing password
        response3 = client.post(
            "/api/auth/register",
            json={"username": "testuser", "email": "test@example.com"},
        )
        assert response3.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# =============================================================================
# Login Tests
# =============================================================================


class TestUserLogin:
    """Tests for POST /api/auth/login endpoint."""

    def test_login_returns_tokens_on_success(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that successful login returns JWT tokens."""
        # Mock successful authentication
        mock_user = MagicMock()
        mock_user.id = "user1"
        mock_user.username = "testuser"
        mock_user.email = "test@example.com"
        mock_user.is_admin = False

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute.return_value = mock_result

        login_data = {
            "username": "testuser",
            "password": "SecurePassword123!",  # pragma: allowlist secret
        }

        response = client.post("/api/auth/login", json=login_data)

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        assert data["user"]["username"] == "testuser"

    def test_login_fails_with_wrong_password(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that login fails with incorrect password."""
        # Mock user exists but password is wrong
        mock_user = MagicMock()
        mock_user.id = "user1"
        mock_user.username = "testuser"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute.return_value = mock_result

        login_data = {
            "username": "testuser",
            "password": "WrongPassword123!",  # pragma: allowlist secret
        }

        response = client.post("/api/auth/login", json=login_data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        assert "detail" in data
        assert "credentials" in data["detail"].lower()

    def test_login_fails_with_unknown_user(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that login fails for non-existent user."""
        # Mock no user found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        login_data = {
            "username": "nonexistent",
            "password": "Password123!",  # pragma: allowlist secret
        }

        response = client.post("/api/auth/login", json=login_data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        assert "detail" in data
        assert "credentials" in data["detail"].lower()

    def test_login_sets_session_cookie(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that successful login sets session cookie."""
        # Mock successful authentication
        mock_user = MagicMock()
        mock_user.id = "user1"
        mock_user.username = "testuser"
        mock_user.is_admin = False

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute.return_value = mock_result

        login_data = {
            "username": "testuser",
            "password": "SecurePassword123!",  # pragma: allowlist secret
        }

        response = client.post("/api/auth/login", json=login_data)

        assert response.status_code == 200
        # Check for Set-Cookie header
        assert "set-cookie" in response.headers
        cookie_header = response.headers["set-cookie"]
        assert "session" in cookie_header.lower()
        assert "httponly" in cookie_header.lower()
        assert "secure" in cookie_header.lower()

    def test_login_validates_required_fields(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that login validates required fields."""
        # Missing username
        response1 = client.post(
            "/api/auth/login",
            json={"password": "Password123!"},  # pragma: allowlist secret
        )
        assert response1.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Missing password
        response2 = client.post("/api/auth/login", json={"username": "testuser"})
        assert response2.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# =============================================================================
# Logout Tests
# =============================================================================


class TestUserLogout:
    """Tests for POST /api/auth/logout endpoint."""

    def test_logout_clears_session(self, client: TestClient, mock_db_session: AsyncMock) -> None:
        """Test that logout clears session cookie."""
        response = client.post("/api/auth/logout", headers={"Authorization": "Bearer fake_token"})

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "logout" in data["message"].lower()

        # Check that Set-Cookie header clears the session
        if "set-cookie" in response.headers:
            cookie_header = response.headers["set-cookie"]
            assert "max-age=0" in cookie_header.lower() or "expires" in cookie_header.lower()

    def test_logout_requires_auth(self, client: TestClient, mock_db_session: AsyncMock) -> None:
        """Test that logout requires authentication."""
        # No auth header
        response = client.post("/api/auth/logout")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# =============================================================================
# Current User Tests
# =============================================================================


class TestCurrentUser:
    """Tests for GET /api/auth/me endpoint."""

    def test_me_returns_current_user(self, client: TestClient, mock_db_session: AsyncMock) -> None:
        """Test that /me returns current user info."""
        # Mock authenticated user
        mock_user = MagicMock()
        mock_user.id = "user1"
        mock_user.username = "testuser"
        mock_user.email = "test@example.com"
        mock_user.is_admin = False
        mock_user.created_at = datetime(2025, 1, 1, 12, 0, 0)

        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer fake_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
        assert data["is_admin"] is False
        # Password should NOT be in response
        assert "password" not in data
        assert "password_hash" not in data

    def test_me_requires_auth(self, client: TestClient, mock_db_session: AsyncMock) -> None:
        """Test that /me requires authentication."""
        # No auth header
        response = client.get("/api/auth/me")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_me_fails_with_invalid_token(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that /me fails with invalid token."""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid_token"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
