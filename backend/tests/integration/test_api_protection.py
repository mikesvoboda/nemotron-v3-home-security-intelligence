"""Integration tests for API protection during setup window.

Tests the complete API protection flow from initial setup through
user registration and authentication. These tests verify that:
1. All endpoints return 503 before setup (except whitelist)
2. Setup flow enables endpoints after first user
3. Authentication is required after setup
4. Multiple auth methods work (JWT, API key, session)

These tests MUST FAIL initially (RED phase of TDD) as the middleware,
endpoints, and services don't exist yet.

Test Coverage:
- Complete setup flow from empty system to authenticated access
- 503 protection for all non-whitelisted endpoints
- Authentication requirement after setup
- JWT token authentication
- API key authentication
- Session cookie authentication
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient

# Mark as integration tests
pytestmark = pytest.mark.integration


# =============================================================================
# Pre-Setup Protection Tests
# =============================================================================


class TestPreSetupProtection:
    """Tests for endpoint protection before first user setup."""

    @pytest.mark.asyncio
    async def test_all_endpoints_return_503_before_setup(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that all non-whitelisted endpoints return 503 before setup."""
        # List of endpoints that should be blocked
        blocked_endpoints = [
            ("GET", "/api/cameras"),
            ("POST", "/api/cameras"),
            ("GET", "/api/events"),
            ("POST", "/api/events"),
            ("GET", "/api/detections"),
            ("GET", "/api/zones"),
            ("POST", "/api/zones"),
            ("GET", "/api/alerts"),
            ("POST", "/api/alerts"),
            ("GET", "/api/system/stats"),
            ("GET", "/api/system/metrics"),
            ("GET", "/api/admin/seed/cameras"),
            ("POST", "/api/admin/seed/cameras"),
        ]

        for method, endpoint in blocked_endpoints:
            if method == "GET":
                response = await client.get(endpoint)
            elif method == "POST":
                response = await client.post(endpoint, json={})
            else:
                pytest.fail(f"Unsupported method: {method}")

            assert response.status_code == 503, f"Expected 503 for {method} {endpoint}"
            data = response.json()
            assert "detail" in data
            assert "setup" in data["detail"].lower()
            assert "setup_url" in data
            assert "code" in data
            assert data["code"] == "setup_required"

    @pytest.mark.asyncio
    async def test_whitelisted_endpoints_accessible_before_setup(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that whitelisted endpoints are accessible before setup."""
        whitelisted_endpoints = [
            "/api/auth/setup-status",
            "/health",
            "/ready",
            "/api/system/health",
        ]

        for endpoint in whitelisted_endpoints:
            response = await client.get(endpoint)

            # Should NOT return 503
            assert response.status_code != 503, f"Endpoint {endpoint} should not be blocked"
            # Most will return 200, but some might return other success codes
            assert response.status_code < 400, f"Expected success for {endpoint}"

    @pytest.mark.asyncio
    async def test_register_endpoint_accessible_before_setup(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that registration endpoint is accessible before setup."""
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "admin",
                "email": "admin@example.com",
                "password": "SecurePassword123!",  # pragma: allowlist secret
            },
        )

        # Should NOT return 503
        assert response.status_code != 503
        # Should create user (201) or have validation error (422), but not 503
        assert response.status_code in [201, 422]

    @pytest.mark.asyncio
    async def test_503_response_structure(self, client: AsyncClient, clean_tables: None) -> None:
        """Test that 503 response has proper structure."""
        response = await client.get("/api/cameras")

        assert response.status_code == 503
        data = response.json()

        # Verify response structure
        assert "detail" in data
        assert "setup_url" in data
        assert "code" in data
        assert isinstance(data["detail"], str)
        assert isinstance(data["setup_url"], str)
        assert isinstance(data["code"], str)
        assert data["code"] == "setup_required"


# =============================================================================
# Setup Flow Tests
# =============================================================================


class TestSetupFlow:
    """Tests for complete setup flow enabling endpoints."""

    @pytest.mark.asyncio
    async def test_setup_flow_enables_endpoints(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that completing setup enables all endpoints."""
        # Step 1: Verify we need setup
        status_response = await client.get("/api/auth/setup-status")
        assert status_response.status_code == 200
        assert status_response.json()["needs_setup"] is True

        # Step 2: Verify endpoints are blocked
        cameras_before = await client.get("/api/cameras")
        assert cameras_before.status_code == 503

        # Step 3: Register first user
        register_response = await client.post(
            "/api/auth/register",
            json={
                "username": "admin",
                "email": "admin@example.com",
                "password": "SecurePassword123!",  # pragma: allowlist secret
            },
        )
        assert register_response.status_code == 201
        user_data = register_response.json()
        assert user_data["is_admin"] is True

        # Step 4: Wait for cache to refresh
        await asyncio.sleep(1.5)

        # Step 5: Verify setup complete
        status_after = await client.get("/api/auth/setup-status")
        assert status_after.status_code == 200
        assert status_after.json()["needs_setup"] is False

        # Step 6: Login to get auth token
        login_response = await client.post(
            "/api/auth/login",
            json={
                "username": "admin",
                "password": "SecurePassword123!",  # pragma: allowlist secret
            },
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]

        # Step 7: Verify endpoints are now accessible (with auth)
        cameras_after = await client.get(
            "/api/cameras", headers={"Authorization": f"Bearer {token}"}
        )
        # Should NOT be 503 anymore
        assert cameras_after.status_code != 503
        # Might be 200 (success) or 401 (auth required), but not 503
        assert cameras_after.status_code in [200, 401]

    @pytest.mark.asyncio
    async def test_setup_prevents_second_registration(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that registration is disabled after first user."""
        # Register first user
        first_reg = await client.post(
            "/api/auth/register",
            json={
                "username": "admin",
                "email": "admin@example.com",
                "password": "SecurePassword123!",  # pragma: allowlist secret
            },
        )
        assert first_reg.status_code == 201

        # Try to register second user
        second_reg = await client.post(
            "/api/auth/register",
            json={
                "username": "hacker",
                "email": "hacker@example.com",
                "password": "Password123!",  # pragma: allowlist secret
            },
        )
        assert second_reg.status_code == 403
        data = second_reg.json()
        assert "registration" in data["detail"].lower()
        assert "disabled" in data["detail"].lower()


# =============================================================================
# Post-Setup Authentication Tests
# =============================================================================


class TestPostSetupAuthentication:
    """Tests for authentication requirement after setup."""

    @pytest.mark.asyncio
    async def test_auth_required_after_setup(self, client: AsyncClient, clean_tables: None) -> None:
        """Test that endpoints require auth after setup."""
        # Complete setup
        await client.post(
            "/api/auth/register",
            json={
                "username": "admin",
                "email": "admin@example.com",
                "password": "SecurePassword123!",  # pragma: allowlist secret
            },
        )

        await asyncio.sleep(1.5)  # Wait for cache

        # Try to access endpoints without auth
        endpoints = [
            "/api/cameras",
            "/api/events",
            "/api/detections",
            "/api/zones",
        ]

        for endpoint in endpoints:
            response = await client.get(endpoint)

            # Should NOT be 503 (setup complete)
            assert response.status_code != 503
            # Should require authentication (401)
            assert response.status_code == 401, f"Expected 401 for {endpoint}"

    @pytest.mark.asyncio
    async def test_jwt_auth_works(self, client: AsyncClient, clean_tables: None) -> None:
        """Test that JWT authentication works after setup."""
        # Register and login
        await client.post(
            "/api/auth/register",
            json={
                "username": "admin",
                "email": "admin@example.com",
                "password": "SecurePassword123!",  # pragma: allowlist secret
            },
        )

        login_response = await client.post(
            "/api/auth/login",
            json={
                "username": "admin",
                "password": "SecurePassword123!",  # pragma: allowlist secret
            },
        )
        token = login_response.json()["access_token"]

        await asyncio.sleep(1.5)  # Wait for cache

        # Access endpoint with JWT
        response = await client.get("/api/cameras", headers={"Authorization": f"Bearer {token}"})

        # Should succeed or return empty list, not 401 or 503
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_invalid_jwt_rejected(self, client: AsyncClient, clean_tables: None) -> None:
        """Test that invalid JWT tokens are rejected."""
        # Complete setup
        await client.post(
            "/api/auth/register",
            json={
                "username": "admin",
                "email": "admin@example.com",
                "password": "SecurePassword123!",  # pragma: allowlist secret
            },
        )

        await asyncio.sleep(1.5)

        # Try with invalid token
        response = await client.get(
            "/api/cameras", headers={"Authorization": "Bearer invalid_token"}
        )

        assert response.status_code == 401


# =============================================================================
# API Key Authentication Tests
# =============================================================================


class TestApiKeyAuthentication:
    """Tests for API key authentication after setup."""

    @pytest.mark.asyncio
    async def test_api_key_auth_works(self, client: AsyncClient, clean_tables: None) -> None:
        """Test that API key authentication works after setup."""
        # Complete setup and login
        await client.post(
            "/api/auth/register",
            json={
                "username": "admin",
                "email": "admin@example.com",
                "password": "SecurePassword123!",  # pragma: allowlist secret
            },
        )

        login_response = await client.post(
            "/api/auth/login",
            json={
                "username": "admin",
                "password": "SecurePassword123!",  # pragma: allowlist secret
            },
        )
        token = login_response.json()["access_token"]

        await asyncio.sleep(1.5)

        # Create API key
        api_key_response = await client.post(
            "/api/auth/api-keys",
            json={"name": "test-key"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert api_key_response.status_code == 201
        api_key = api_key_response.json()["key"]

        # Use API key to access endpoint
        response = await client.get("/api/cameras", headers={"X-API-Key": api_key})

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_invalid_api_key_rejected(self, client: AsyncClient, clean_tables: None) -> None:
        """Test that invalid API keys are rejected."""
        # Complete setup
        await client.post(
            "/api/auth/register",
            json={
                "username": "admin",
                "email": "admin@example.com",
                "password": "SecurePassword123!",  # pragma: allowlist secret
            },
        )

        await asyncio.sleep(1.5)

        # Try with invalid API key
        response = await client.get("/api/cameras", headers={"X-API-Key": "invalid_key"})

        assert response.status_code == 401


# =============================================================================
# Session Cookie Authentication Tests
# =============================================================================


class TestSessionCookieAuthentication:
    """Tests for session cookie authentication after setup."""

    @pytest.mark.asyncio
    async def test_session_cookie_auth_works(self, client: AsyncClient, clean_tables: None) -> None:
        """Test that session cookies work for authentication."""
        # Complete setup and login
        await client.post(
            "/api/auth/register",
            json={
                "username": "admin",
                "email": "admin@example.com",
                "password": "SecurePassword123!",  # pragma: allowlist secret
            },
        )

        # Login (should set session cookie)
        login_response = await client.post(
            "/api/auth/login",
            json={
                "username": "admin",
                "password": "SecurePassword123!",  # pragma: allowlist secret
            },
        )
        assert "set-cookie" in login_response.headers

        await asyncio.sleep(1.5)

        # Subsequent requests should work with cookies
        # (AsyncClient automatically handles cookies)
        response = await client.get("/api/cameras")

        # Should work with session cookie
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_session_logout_clears_cookie(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that logout clears session cookie."""
        # Setup and login
        await client.post(
            "/api/auth/register",
            json={
                "username": "admin",
                "email": "admin@example.com",
                "password": "SecurePassword123!",  # pragma: allowlist secret
            },
        )

        login_response = await client.post(
            "/api/auth/login",
            json={
                "username": "admin",
                "password": "SecurePassword123!",  # pragma: allowlist secret
            },
        )
        token = login_response.json()["access_token"]

        await asyncio.sleep(1.5)

        # Logout
        logout_response = await client.post(
            "/api/auth/logout", headers={"Authorization": f"Bearer {token}"}
        )
        assert logout_response.status_code == 200

        # Verify cookie is cleared
        if "set-cookie" in logout_response.headers:
            cookie_header = logout_response.headers["set-cookie"]
            assert "max-age=0" in cookie_header.lower() or "expires" in cookie_header.lower()


# =============================================================================
# Multi-User Flow Tests
# =============================================================================


class TestMultiUserFlow:
    """Tests for admin creating additional users after setup."""

    @pytest.mark.asyncio
    async def test_admin_can_create_additional_users(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that admin can create additional users after setup."""
        # Setup first admin user
        await client.post(
            "/api/auth/register",
            json={
                "username": "admin",
                "email": "admin@example.com",
                "password": "SecurePassword123!",  # pragma: allowlist secret
            },
        )

        # Login as admin
        login_response = await client.post(
            "/api/auth/login",
            json={
                "username": "admin",
                "password": "SecurePassword123!",  # pragma: allowlist secret
            },
        )
        admin_token = login_response.json()["access_token"]

        await asyncio.sleep(1.5)

        # Create second user as admin
        create_user_response = await client.post(
            "/api/admin/users",
            json={
                "username": "user2",
                "email": "user2@example.com",
                "password": "Password123!",  # pragma: allowlist secret
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert create_user_response.status_code == 201
        user_data = create_user_response.json()
        assert user_data["username"] == "user2"
        assert user_data["is_admin"] is False

    @pytest.mark.asyncio
    async def test_non_admin_cannot_create_users(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that non-admin users cannot create users."""
        # Setup first admin
        await client.post(
            "/api/auth/register",
            json={
                "username": "admin",
                "email": "admin@example.com",
                "password": "SecurePassword123!",  # pragma: allowlist secret
            },
        )

        # Admin creates regular user
        login_response = await client.post(
            "/api/auth/login",
            json={
                "username": "admin",
                "password": "SecurePassword123!",  # pragma: allowlist secret
            },
        )
        admin_token = login_response.json()["access_token"]

        await asyncio.sleep(1.5)

        await client.post(
            "/api/admin/users",
            json={
                "username": "regularuser",
                "email": "regular@example.com",
                "password": "Password123!",  # pragma: allowlist secret
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        # Login as regular user
        user_login = await client.post(
            "/api/auth/login",
            json={
                "username": "regularuser",
                "password": "Password123!",  # pragma: allowlist secret
            },
        )
        user_token = user_login.json()["access_token"]

        # Try to create user as non-admin
        create_response = await client.post(
            "/api/admin/users",
            json={
                "username": "user3",
                "email": "user3@example.com",
                "password": "Password123!",  # pragma: allowlist secret
            },
            headers={"Authorization": f"Bearer {user_token}"},
        )

        assert create_response.status_code == 403
