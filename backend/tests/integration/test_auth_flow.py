"""Integration tests for authentication flow.

Tests cover complete authentication workflows including user registration,
login, token refresh, and API key authentication. These tests MUST FAIL
initially (RED phase of TDD) as the endpoints and services don't exist yet.

Test Categories:
- User registration flow
- User login with tokens
- Token refresh workflow
- API key creation and usage
- Error scenarios
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from fastapi import status

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

# Mark as integration tests
pytestmark = pytest.mark.integration


# =============================================================================
# User Registration Tests
# =============================================================================


class TestUserRegistration:
    """Tests for user registration flow."""

    @pytest.mark.asyncio
    async def test_user_registration_creates_user(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that user registration creates a new user."""
        registration_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "SecurePassword123!",  # pragma: allowlist secret
        }

        response = await client.post("/api/auth/register", json=registration_data)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "id" in data
        assert data["username"] == "newuser"
        assert data["email"] == "newuser@example.com"
        # Password should NOT be in response
        assert "password" not in data
        assert "password_hash" not in data

    @pytest.mark.asyncio
    async def test_user_registration_duplicate_email(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that registering with duplicate email fails."""
        registration_data = {
            "username": "user1",
            "email": "duplicate@example.com",
            "password": "Password123!",  # pragma: allowlist secret
        }

        # First registration should succeed
        response1 = await client.post("/api/auth/register", json=registration_data)
        assert response1.status_code == status.HTTP_201_CREATED

        # Second registration with same email should fail
        registration_data["username"] = "user2"  # Different username
        response2 = await client.post("/api/auth/register", json=registration_data)
        assert response2.status_code == status.HTTP_409_CONFLICT

    @pytest.mark.asyncio
    async def test_user_registration_duplicate_username(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that registering with duplicate username fails."""
        registration_data = {
            "username": "duplicateuser",
            "email": "user1@example.com",
            "password": "Password123!",  # pragma: allowlist secret
        }

        response1 = await client.post("/api/auth/register", json=registration_data)
        assert response1.status_code == status.HTTP_201_CREATED

        # Second registration with same username should fail
        registration_data["email"] = "user2@example.com"  # Different email
        response2 = await client.post("/api/auth/register", json=registration_data)
        assert response2.status_code == status.HTTP_409_CONFLICT

    @pytest.mark.asyncio
    async def test_user_registration_weak_password(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that weak passwords are rejected."""
        registration_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "weak",  # pragma: allowlist secret
        }

        response = await client.post("/api/auth/register", json=registration_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_user_registration_invalid_email(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that invalid email format is rejected."""
        registration_data = {
            "username": "testuser",
            "email": "not_an_email",
            "password": "SecurePassword123!",  # pragma: allowlist secret
        }

        response = await client.post("/api/auth/register", json=registration_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_user_registration_empty_fields(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that empty required fields are rejected."""
        registration_data = {
            "username": "",
            "email": "",
            "password": "",
        }

        response = await client.post("/api/auth/register", json=registration_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# =============================================================================
# User Login Tests
# =============================================================================


class TestUserLogin:
    """Tests for user login flow."""

    @pytest.mark.asyncio
    async def test_user_login_returns_tokens(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that successful login returns access and refresh tokens."""
        # First register a user
        registration_data = {
            "username": "loginuser",
            "email": "login@example.com",
            "password": "SecurePassword123!",  # pragma: allowlist secret
        }
        await client.post("/api/auth/register", json=registration_data)

        # Then login
        login_data = {"username": "loginuser", "password": "SecurePassword123!"}  # pragma: allowlist secret
        response = await client.post("/api/auth/login", json=login_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_user_login_wrong_password_fails(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that login with wrong password fails."""
        # Register user
        registration_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "CorrectPassword123!",  # pragma: allowlist secret
        }
        await client.post("/api/auth/register", json=registration_data)

        # Try to login with wrong password
        login_data = {"username": "testuser", "password": "WrongPassword123!"}  # pragma: allowlist secret
        response = await client.post("/api/auth/login", json=login_data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_user_login_nonexistent_user(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that login with nonexistent username fails."""
        login_data = {
            "username": "nonexistent",
            "password": "Password123!",  # pragma: allowlist secret
        }
        response = await client.post("/api/auth/login", json=login_data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_user_login_by_email(self, client: AsyncClient, clean_tables: None) -> None:
        """Test that users can login using email instead of username."""
        # Register user
        registration_data = {
            "username": "emailuser",
            "email": "email@example.com",
            "password": "Password123!",  # pragma: allowlist secret
        }
        await client.post("/api/auth/register", json=registration_data)

        # Login with email
        login_data = {"email": "email@example.com", "password": "Password123!"}  # pragma: allowlist secret
        response = await client.post("/api/auth/login", json=login_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data

    @pytest.mark.asyncio
    async def test_user_login_inactive_account(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that login with inactive account fails."""
        # This test would require setting up an inactive user
        # Implementation depends on user activation workflow
        pass


# =============================================================================
# Token Refresh Tests
# =============================================================================


class TestTokenRefresh:
    """Tests for token refresh workflow."""

    @pytest.mark.asyncio
    async def test_token_refresh_works(self, client: AsyncClient, clean_tables: None) -> None:
        """Test that refresh token can be used to get new access token."""
        # Register and login
        registration_data = {
            "username": "refreshuser",
            "email": "refresh@example.com",
            "password": "Password123!",  # pragma: allowlist secret
        }
        await client.post("/api/auth/register", json=registration_data)

        login_response = await client.post(
            "/api/auth/login",
            json={"username": "refreshuser", "password": "Password123!"},  # pragma: allowlist secret
        )
        tokens = login_response.json()
        refresh_token = tokens["refresh_token"]

        # Use refresh token to get new access token
        refresh_response = await client.post(
            "/api/auth/refresh", json={"refresh_token": refresh_token}
        )

        assert refresh_response.status_code == status.HTTP_200_OK
        new_tokens = refresh_response.json()
        assert "access_token" in new_tokens
        assert "refresh_token" in new_tokens
        # New access token should be different from old one
        assert new_tokens["access_token"] != tokens["access_token"]

    @pytest.mark.asyncio
    async def test_token_refresh_invalid_token(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that invalid refresh token is rejected."""
        refresh_response = await client.post(
            "/api/auth/refresh", json={"refresh_token": "invalid.token.here"}
        )

        assert refresh_response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_token_refresh_expired_token(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that expired refresh token is rejected."""
        # This would require creating an expired token
        # Implementation depends on token creation utilities
        pass

    @pytest.mark.asyncio
    async def test_token_refresh_access_token_fails(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that using access token for refresh fails."""
        # Register and login
        registration_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "Password123!",  # pragma: allowlist secret
        }
        await client.post("/api/auth/register", json=registration_data)

        login_response = await client.post(
            "/api/auth/login",
            json={"username": "testuser", "password": "Password123!"},  # pragma: allowlist secret
        )
        tokens = login_response.json()
        access_token = tokens["access_token"]

        # Try to use access token for refresh (should fail)
        refresh_response = await client.post(
            "/api/auth/refresh", json={"refresh_token": access_token}
        )

        assert refresh_response.status_code == status.HTTP_401_UNAUTHORIZED


# =============================================================================
# API Key Tests
# =============================================================================


class TestAPIKeyAuthentication:
    """Tests for API key creation and authentication."""

    @pytest.mark.asyncio
    async def test_api_key_creation(self, client: AsyncClient, clean_tables: None) -> None:
        """Test creating an API key for a user."""
        # Register and login to get access token
        registration_data = {
            "username": "apiuser",
            "email": "api@example.com",
            "password": "Password123!",  # pragma: allowlist secret
        }
        await client.post("/api/auth/register", json=registration_data)

        login_response = await client.post(
            "/api/auth/login",
            json={"username": "apiuser", "password": "Password123!"},  # pragma: allowlist secret
        )
        access_token = login_response.json()["access_token"]

        # Create API key
        api_key_data = {"name": "Test API Key"}
        response = await client.post(
            "/api/auth/api-keys",
            json=api_key_data,
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "api_key" in data  # Plaintext key returned only once
        assert "prefix" in data
        assert data["api_key"].startswith("nemo_k1_")
        assert data["name"] == "Test API Key"

    @pytest.mark.asyncio
    async def test_api_key_authentication(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that API key can be used for authentication."""
        # Register user and create API key
        registration_data = {
            "username": "apiuser",
            "email": "api@example.com",
            "password": "Password123!",  # pragma: allowlist secret
        }
        await client.post("/api/auth/register", json=registration_data)

        login_response = await client.post(
            "/api/auth/login",
            json={"username": "apiuser", "password": "Password123!"},  # pragma: allowlist secret
        )
        access_token = login_response.json()["access_token"]

        api_key_response = await client.post(
            "/api/auth/api-keys",
            json={"name": "Test Key"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        api_key = api_key_response.json()["api_key"]

        # Use API key to access protected endpoint
        response = await client.get(
            "/api/cameras", headers={"X-API-Key": api_key}
        )

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_api_key_invalid(self, client: AsyncClient, clean_tables: None) -> None:
        """Test that invalid API key is rejected."""
        response = await client.get(
            "/api/cameras", headers={"X-API-Key": "nemo_k1_invalid_key"}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_api_key_list_user_keys(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test listing user's API keys."""
        # Register and create API keys
        registration_data = {
            "username": "multikey",
            "email": "multi@example.com",
            "password": "Password123!",  # pragma: allowlist secret
        }
        await client.post("/api/auth/register", json=registration_data)

        login_response = await client.post(
            "/api/auth/login",
            json={"username": "multikey", "password": "Password123!"},  # pragma: allowlist secret
        )
        access_token = login_response.json()["access_token"]

        # Create two API keys
        await client.post(
            "/api/auth/api-keys",
            json={"name": "Key 1"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        await client.post(
            "/api/auth/api-keys",
            json={"name": "Key 2"},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        # List API keys
        response = await client.get(
            "/api/auth/api-keys",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
        # Plaintext keys should NOT be in list response
        for key in data:
            assert "api_key" not in key
            assert "prefix" in key
            assert "name" in key

    @pytest.mark.asyncio
    async def test_api_key_revoke(self, client: AsyncClient, clean_tables: None) -> None:
        """Test revoking an API key."""
        # Register and create API key
        registration_data = {
            "username": "revokeuser",
            "email": "revoke@example.com",
            "password": "Password123!",  # pragma: allowlist secret
        }
        await client.post("/api/auth/register", json=registration_data)

        login_response = await client.post(
            "/api/auth/login",
            json={"username": "revokeuser", "password": "Password123!"},  # pragma: allowlist secret
        )
        access_token = login_response.json()["access_token"]

        api_key_response = await client.post(
            "/api/auth/api-keys",
            json={"name": "To Revoke"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        api_key = api_key_response.json()["api_key"]
        key_id = api_key_response.json()["id"]

        # API key should work
        response1 = await client.get("/api/cameras", headers={"X-API-Key": api_key})
        assert response1.status_code == status.HTTP_200_OK

        # Revoke the key
        revoke_response = await client.delete(
            f"/api/auth/api-keys/{key_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert revoke_response.status_code == status.HTTP_204_NO_CONTENT

        # API key should no longer work
        response2 = await client.get("/api/cameras", headers={"X-API-Key": api_key})
        assert response2.status_code == status.HTTP_401_UNAUTHORIZED


# =============================================================================
# Protected Endpoint Access Tests
# =============================================================================


class TestProtectedEndpointAccess:
    """Tests for accessing protected endpoints with authentication."""

    @pytest.mark.asyncio
    async def test_protected_endpoint_requires_auth(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that protected endpoints require authentication."""
        # Try to access without authentication
        response = await client.get("/api/cameras")

        # Should return 401 if auth is enabled, or 200 if disabled
        # Behavior depends on AUTH_ENABLED setting
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_200_OK]

    @pytest.mark.asyncio
    async def test_protected_endpoint_with_token(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test accessing protected endpoint with valid token."""
        # Register and login
        registration_data = {
            "username": "protected",
            "email": "protected@example.com",
            "password": "Password123!",  # pragma: allowlist secret
        }
        await client.post("/api/auth/register", json=registration_data)

        login_response = await client.post(
            "/api/auth/login",
            json={"username": "protected", "password": "Password123!"},  # pragma: allowlist secret
        )
        access_token = login_response.json()["access_token"]

        # Access protected endpoint with token
        response = await client.get(
            "/api/cameras", headers={"Authorization": f"Bearer {access_token}"}
        )

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_protected_endpoint_invalid_token(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that invalid token is rejected."""
        response = await client.get(
            "/api/cameras", headers={"Authorization": "Bearer invalid.token.here"}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_protected_endpoint_expired_token(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that expired token is rejected."""
        # Would require creating an expired token
        pass


# =============================================================================
# Logout and Session Management Tests
# =============================================================================


class TestLogoutAndSessions:
    """Tests for logout and session management."""

    @pytest.mark.asyncio
    async def test_user_logout(self, client: AsyncClient, clean_tables: None) -> None:
        """Test that logout invalidates the session."""
        # Register and login
        registration_data = {
            "username": "logoutuser",
            "email": "logout@example.com",
            "password": "Password123!",  # pragma: allowlist secret
        }
        await client.post("/api/auth/register", json=registration_data)

        login_response = await client.post(
            "/api/auth/login",
            json={"username": "logoutuser", "password": "Password123!"},  # pragma: allowlist secret
        )
        access_token = login_response.json()["access_token"]

        # Logout
        logout_response = await client.post(
            "/api/auth/logout", headers={"Authorization": f"Bearer {access_token}"}
        )

        assert logout_response.status_code == status.HTTP_200_OK

        # Token should no longer work (if session-based)
        # This depends on whether we use stateless JWT or session-based auth

    @pytest.mark.asyncio
    async def test_user_can_have_multiple_sessions(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that user can have multiple active sessions."""
        # Register user
        registration_data = {
            "username": "multisession",
            "email": "multi@example.com",
            "password": "Password123!",  # pragma: allowlist secret
        }
        await client.post("/api/auth/register", json=registration_data)

        # Login twice (simulate two devices)
        login_response1 = await client.post(
            "/api/auth/login",
            json={"username": "multisession", "password": "Password123!"},  # pragma: allowlist secret
        )
        login_response2 = await client.post(
            "/api/auth/login",
            json={"username": "multisession", "password": "Password123!"},  # pragma: allowlist secret
        )

        token1 = login_response1.json()["access_token"]
        token2 = login_response2.json()["access_token"]

        # Both tokens should work
        response1 = await client.get(
            "/api/cameras", headers={"Authorization": f"Bearer {token1}"}
        )
        response2 = await client.get(
            "/api/cameras", headers={"Authorization": f"Bearer {token2}"}
        )

        assert response1.status_code == status.HTTP_200_OK
        assert response2.status_code == status.HTTP_200_OK
