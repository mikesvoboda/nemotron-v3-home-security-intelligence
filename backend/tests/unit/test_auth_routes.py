"""Unit tests for auth routes (NEM-5312: Phase 2 API Protection).

Tests cover:
- Setup status endpoint
- User registration (first admin user)
- Login/logout with session management
- Current user endpoint
- API key management (CRUD)
- Setup guard middleware
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.auth import (
    APIKeyCreateRequest,
    UserLoginRequest,
    UserRegisterRequest,
)

# =============================================================================
# Test: Auth Schemas
# =============================================================================


class TestUserRegisterRequestSchema:
    """Tests for UserRegisterRequest schema validation."""

    def test_valid_registration(self) -> None:
        """Test valid registration data is accepted."""
        request = UserRegisterRequest(
            username="testuser",
            email="test@example.com",
            password="TestPassword123",  # pragma: allowlist secret,
        )
        assert request.username == "testuser"
        assert request.email == "test@example.com"
        assert request.password == "TestPassword123"  # pragma: allowlist secret

    def test_username_too_short(self) -> None:
        """Test username minimum length validation."""
        with pytest.raises(ValueError):
            UserRegisterRequest(
                username="ab",  # Too short (min 3)
                email="test@example.com",
                password="TestPassword123",  # pragma: allowlist secret,
            )

    def test_username_invalid_characters(self) -> None:
        """Test username pattern validation (alphanumeric, underscores, hyphens)."""
        with pytest.raises(ValueError):
            UserRegisterRequest(
                username="test user",  # Contains space
                email="test@example.com",
                password="TestPassword123",  # pragma: allowlist secret,
            )

    def test_invalid_email_format(self) -> None:
        """Test email format validation."""
        with pytest.raises(ValueError):
            UserRegisterRequest(
                username="testuser",
                email="not-an-email",
                password="TestPassword123",  # pragma: allowlist secret,
            )

    def test_password_too_short(self) -> None:
        """Test password minimum length validation (12 chars)."""
        with pytest.raises(ValueError):
            UserRegisterRequest(
                username="testuser",
                email="test@example.com",
                password="Short1",  # Too short  # pragma: allowlist secret
            )

    def test_password_no_uppercase(self) -> None:
        """Test password requires uppercase letter."""
        with pytest.raises(ValueError):
            UserRegisterRequest(
                username="testuser",
                email="test@example.com",
                password="testpassword123",  # No uppercase  # pragma: allowlist secret
            )

    def test_password_no_lowercase(self) -> None:
        """Test password requires lowercase letter."""
        with pytest.raises(ValueError):
            UserRegisterRequest(
                username="testuser",
                email="test@example.com",
                password="TESTPASSWORD123",  # No lowercase  # pragma: allowlist secret
            )

    def test_password_no_digit(self) -> None:
        """Test password requires at least one digit."""
        with pytest.raises(ValueError):
            UserRegisterRequest(
                username="testuser",
                email="test@example.com",
                password="TestPasswordNoDigit",  # No digit  # pragma: allowlist secret
            )


class TestUserLoginRequestSchema:
    """Tests for UserLoginRequest schema validation."""

    def test_valid_login(self) -> None:
        """Test valid login data is accepted."""
        request = UserLoginRequest(
            username="testuser",
            password="password123",  # pragma: allowlist secret
        )
        assert request.username == "testuser"
        assert request.password == "password123"  # pragma: allowlist secret

    def test_empty_username(self) -> None:
        """Test empty username is rejected."""
        with pytest.raises(ValueError):
            UserLoginRequest(username="", password="password123")  # pragma: allowlist secret

    def test_empty_password(self) -> None:
        """Test empty password is rejected."""
        with pytest.raises(ValueError):
            UserLoginRequest(username="testuser", password="")


class TestAPIKeyCreateRequestSchema:
    """Tests for APIKeyCreateRequest schema validation."""

    def test_valid_api_key_request(self) -> None:
        """Test valid API key creation request."""
        request = APIKeyCreateRequest(
            name="My API Key",
            expires_in_days=30,
        )
        assert request.name == "My API Key"
        assert request.expires_in_days == 30

    def test_api_key_no_expiration(self) -> None:
        """Test API key request with no expiration (permanent key)."""
        request = APIKeyCreateRequest(
            name="Permanent Key",
            expires_in_days=None,
        )
        assert request.name == "Permanent Key"
        assert request.expires_in_days is None

    def test_api_key_name_too_long(self) -> None:
        """Test API key name max length validation."""
        with pytest.raises(ValueError):
            APIKeyCreateRequest(
                name="A" * 101,  # Too long (max 100)
                expires_in_days=30,
            )

    def test_api_key_expiration_too_long(self) -> None:
        """Test API key expiration max days validation."""
        with pytest.raises(ValueError):
            APIKeyCreateRequest(
                name="My Key",
                expires_in_days=366,  # Too long (max 365)
            )


# =============================================================================
# Test: Setup Status Endpoint
# =============================================================================


class TestSetupStatusEndpoint:
    """Tests for GET /api/auth/setup-status endpoint."""

    @pytest.mark.asyncio
    async def test_setup_required_when_no_users(self) -> None:
        """Test setup is required when no users exist."""
        from backend.api.routes.auth import get_setup_status

        # Mock database session with no users
        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_db.execute.return_value = mock_result

        response = await get_setup_status(db=mock_db)

        assert response.setup_required is True

    @pytest.mark.asyncio
    async def test_setup_not_required_when_users_exist(self) -> None:
        """Test setup is not required when users exist."""
        from backend.api.routes.auth import get_setup_status

        # Mock database session with existing users
        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        mock_db.execute.return_value = mock_result

        response = await get_setup_status(db=mock_db)

        assert response.setup_required is False


# =============================================================================
# Test: User Registration Endpoint
# =============================================================================


class TestUserRegistrationEndpoint:
    """Tests for POST /api/auth/register endpoint."""

    @pytest.mark.asyncio
    async def test_register_first_user_success(self) -> None:
        """Test successful registration of first admin user."""
        from backend.api.routes.auth import register_user

        # Mock database session
        mock_db = AsyncMock(spec=AsyncSession)

        # Mock count query (no users exist)
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        # Mock username check (not taken)
        mock_username_result = MagicMock()
        mock_username_result.scalar_one_or_none.return_value = None

        # Mock email check (not taken)
        mock_email_result = MagicMock()
        mock_email_result.scalar_one_or_none.return_value = None

        # Set up execute to return different results for each call
        mock_db.execute.side_effect = [
            mock_count_result,
            mock_username_result,
            mock_email_result,
        ]

        request = UserRegisterRequest(
            username="admin",
            email="admin@example.com",
            password="AdminPassword123",  # pragma: allowlist secret
        )

        response = await register_user(request=request, db=mock_db)

        assert response.username == "admin"
        assert response.email == "admin@example.com"
        assert response.is_admin is True
        assert response.is_active is True
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_blocked_when_users_exist(self) -> None:
        """Test registration is blocked when users already exist."""
        from backend.api.routes.auth import register_user

        # Mock database session with existing users
        mock_db = AsyncMock(spec=AsyncSession)
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1
        mock_db.execute.return_value = mock_count_result

        request = UserRegisterRequest(
            username="newuser",
            email="new@example.com",
            password="NewPassword123",  # pragma: allowlist secret
        )

        with pytest.raises(HTTPException) as exc_info:
            await register_user(request=request, db=mock_db)

        assert exc_info.value.status_code == status.HTTP_409_CONFLICT
        assert "Registration is closed" in exc_info.value.detail


# =============================================================================
# Test: Login Endpoint
# =============================================================================


class TestLoginEndpoint:
    """Tests for POST /api/auth/login endpoint."""

    @pytest.mark.asyncio
    async def test_login_user_not_found(self) -> None:
        """Test login fails when user doesn't exist."""
        from backend.api.routes.auth import login

        # Mock database session
        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        mock_response = MagicMock()

        request = UserLoginRequest(
            username="nonexistent",
            password="Password123",  # pragma: allowlist secret
        )

        with pytest.raises(HTTPException) as exc_info:
            await login(request=request, response=mock_response, db=mock_db)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid username or password" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_login_invalid_password(self) -> None:
        """Test login fails with wrong password."""
        from backend.api.routes.auth import login
        from backend.models.user import User

        # Create a mock user
        mock_user = MagicMock(spec=User)
        mock_user.id = "user-123"
        mock_user.username = "testuser"
        mock_user.is_active = True
        mock_user.password_hash = "somehash"  # pragma: allowlist secret

        # Mock database session
        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        mock_response = MagicMock()

        request = UserLoginRequest(
            username="testuser",
            password="WrongPassword123",  # pragma: allowlist secret
        )

        # Mock verify_password to return False
        with patch("backend.api.routes.auth.AuthService.verify_password", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await login(request=request, response=mock_response, db=mock_db)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_login_inactive_user(self) -> None:
        """Test login fails for inactive user."""
        from backend.api.routes.auth import login
        from backend.models.user import User

        # Create a mock inactive user
        mock_user = MagicMock(spec=User)
        mock_user.id = "user-123"
        mock_user.username = "testuser"
        mock_user.is_active = False  # User is disabled
        mock_user.password_hash = "somehash"  # pragma: allowlist secret

        # Mock database session
        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        mock_response = MagicMock()

        request = UserLoginRequest(
            username="testuser",
            password="Password123",  # pragma: allowlist secret
        )

        with pytest.raises(HTTPException) as exc_info:
            await login(request=request, response=mock_response, db=mock_db)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Account is disabled" in exc_info.value.detail


# =============================================================================
# Test: Logout Endpoint
# =============================================================================


class TestLogoutEndpoint:
    """Tests for POST /api/auth/logout endpoint."""

    @pytest.mark.asyncio
    async def test_logout_clears_cookie(self) -> None:
        """Test logout clears the session cookie."""
        from backend.api.routes.auth import logout

        mock_response = MagicMock()

        result = await logout(response=mock_response, session_id=None)

        assert result.message == "Logged out successfully"
        mock_response.delete_cookie.assert_called_once()


# =============================================================================
# Test: Current User Endpoint
# =============================================================================


class TestGetCurrentUserDependency:
    """Tests for get_current_user dependency."""

    @pytest.mark.asyncio
    async def test_get_current_user_no_session(self) -> None:
        """Test returns 401 when no session cookie."""
        from backend.api.routes.auth import get_current_user

        mock_db = AsyncMock(spec=AsyncSession)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(session_id=None, db=mock_db)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Not authenticated" in exc_info.value.detail


# =============================================================================
# Test: Setup Guard Middleware
# =============================================================================


class TestSetupGuardMiddleware:
    """Tests for SetupGuardMiddleware."""

    def test_whitelisted_paths(self) -> None:
        """Test whitelisted paths are correctly identified."""
        from backend.api.middleware.setup_guard import (
            SetupGuardMiddleware,
        )

        middleware = SetupGuardMiddleware(app=MagicMock())

        # Test exact matches
        assert middleware._is_whitelisted("/") is True
        assert middleware._is_whitelisted("/health") is True
        assert middleware._is_whitelisted("/ready") is True
        assert middleware._is_whitelisted("/api/auth/setup-status") is True
        assert middleware._is_whitelisted("/api/auth/register") is True

        # Test prefix matches
        assert middleware._is_whitelisted("/docs") is True
        assert middleware._is_whitelisted("/docs/") is True
        assert middleware._is_whitelisted("/redoc") is True

        # Test non-whitelisted paths
        assert middleware._is_whitelisted("/api/cameras") is False
        assert middleware._is_whitelisted("/api/events") is False
        assert middleware._is_whitelisted("/api/auth/login") is False

    def test_whitelist_includes_health_endpoints(self) -> None:
        """Test health endpoints are in whitelist."""
        from backend.api.middleware.setup_guard import SETUP_WHITELIST_EXACT

        assert "/" in SETUP_WHITELIST_EXACT
        assert "/health" in SETUP_WHITELIST_EXACT
        assert "/ready" in SETUP_WHITELIST_EXACT

    def test_whitelist_includes_auth_setup_endpoints(self) -> None:
        """Test auth setup endpoints are in whitelist."""
        from backend.api.middleware.setup_guard import SETUP_WHITELIST_EXACT

        assert "/api/auth/setup-status" in SETUP_WHITELIST_EXACT
        assert "/api/auth/register" in SETUP_WHITELIST_EXACT


# =============================================================================
# Test: Auth Middleware Exempt Paths
# =============================================================================


class TestAuthMiddlewareExemptPaths:
    """Tests for auth middleware exempt paths include auth endpoints."""

    def test_auth_endpoints_exempt(self) -> None:
        """Test auth endpoints are exempt from API key auth."""
        from backend.api.middleware.auth import AuthMiddleware

        middleware = AuthMiddleware(app=MagicMock())

        # These auth endpoints should be exempt
        assert middleware._is_exempt_path("/api/auth/setup-status") is True
        assert middleware._is_exempt_path("/api/auth/register") is True
        assert middleware._is_exempt_path("/api/auth/login") is True

        # Other auth endpoints should NOT be exempt (require auth)
        assert middleware._is_exempt_path("/api/auth/me") is False
        assert middleware._is_exempt_path("/api/auth/logout") is False
        assert middleware._is_exempt_path("/api/auth/api-keys") is False
