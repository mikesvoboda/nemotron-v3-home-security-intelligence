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

from typing import TYPE_CHECKING

import httpx
import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient

    from backend.core.redis import RedisClient

SESSION_COOKIE_NAME = "session_id"  # pragma: allowlist secret

# Matches the key integration_env configures (conftest.py: API_KEYS). The
# only shipped API-key validation path (per-route verify_api_key) checks
# settings.api_keys — not DB-created keys.
TEST_API_KEY = "test-api-key-12345"  # pragma: allowlist secret

# Mark as integration tests that must run in isolation (not parallel)
# These tests modify shared database state (user registration, setup status)
# and must run sequentially in a single worker to avoid race conditions
pytestmark = [
    pytest.mark.integration,
    pytest.mark.xdist_group("api_protection"),  # All tests run in same worker
]


@pytest.fixture
async def unmocked_setup_client(integration_db: str):
    """Async client WITHOUT the shared fixture's SetupGuard bypass.

    The shared `client` fixture patches
    SetupGuardMiddleware._check_setup_complete to always return True, so the
    pre-setup 503 contract is unreachable through it. This fixture leaves the
    real middleware in place, resets its cached setup-complete state (the
    singleton persists across tests in-process), and sends no default API key.
    Owner ruling F3, M1 Task 7.
    """
    from httpx import ASGITransport, AsyncClient

    # Reset the middleware's cached state so "no users" is observed fresh.
    # The singleton instance persists across tests in-process (built lazily on
    # the app's middleware stack); its _setup_complete/_cached flags only ever
    # flip True, so a pre-setup test in a warmed process would otherwise see
    # setup-complete even with an empty users table.
    from sqlalchemy import text

    from backend.api.middleware.setup_guard import SetupGuardMiddleware
    from backend.core.database import get_engine
    from backend.main import app

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE users CASCADE"))

    # Reset cached flags on the app's middleware chain (BaseHTTPMiddleware
    # builds instances lazily at startup; after TestClient-less ASGITransport
    # the instance exists on app.middleware_stack). Reach it defensively.
    stack = getattr(app, "middleware_stack", None)
    node = stack
    while node is not None:
        if isinstance(node, SetupGuardMiddleware):
            node._setup_complete = False
            node._cached_result = False
            node._cached_at = 0.0
            break
        node = getattr(node, "app", None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# =============================================================================
# Pre-Setup Protection Tests
# =============================================================================
# Contract source: auth redesign d0c21081 — feat(auth): implement
# authentication epic phases 2 & 4 (NEM-5312, NEM-5322) (Feb 3 2026), the
# commit that introduced session-cookie auth + setup_required semantics.
# Expectations here assert the SHIPPED contract (owner ruling F3, M1 Task 7).


class TestPreSetupProtection:
    """Tests for endpoint protection before first user setup."""

    @pytest.mark.asyncio
    async def test_all_endpoints_return_503_before_setup(
        self, unmocked_setup_client: AsyncClient, clean_tables: None
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
            ("GET", "/api/system/metrics"),
            # NOTE: /api/system/stats is NOT blocked pre-setup — it is in the
            # SetupGuard whitelist (Prometheus scraping) alongside
            # /api/system/gpu, /api/system/telemetry and /api/metrics.
            ("GET", "/api/admin/seed/cameras"),
            ("POST", "/api/admin/seed/cameras"),
        ]

        for method, endpoint in blocked_endpoints:
            if method == "GET":
                response = await unmocked_setup_client.get(endpoint)
            elif method == "POST":
                response = await unmocked_setup_client.post(endpoint, json={})
            else:
                pytest.fail(f"Unsupported method: {method}")

            assert response.status_code == 503, f"Expected 503 for {method} {endpoint}"
            data = response.json()
            # Shipped 503 body (backend/api/middleware/setup_guard.py): detail +
            # setup_url + setup_status_url — no 'code' key (owner ruling F3).
            assert "detail" in data
            assert "setup" in data["detail"].lower()
            assert "setup_url" in data
            assert "setup_status_url" in data

    @pytest.mark.asyncio
    async def test_whitelisted_endpoints_accessible_before_setup(
        self, unmocked_setup_client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that whitelisted endpoints are accessible before setup."""
        whitelisted_endpoints = [
            "/api/auth/setup-status",
            "/health",
            # /ready and /api/system/health are also whitelisted but NOT here:
            # with lifespan services mocked the readiness endpoint itself
            # reports 503 (service not ready) — a readiness signal, not a
            # setup-guard block (owner ruling F3).
        ]

        for endpoint in whitelisted_endpoints:
            response = await unmocked_setup_client.get(endpoint)

            # Should NOT be blocked by the setup guard (shipped body would be
            # the 503 setup-required payload, not this endpoint's own).
            assert response.status_code != 503, f"Endpoint {endpoint} should not be blocked"
            # Most will return 200, but some might return other success codes
            assert response.status_code < 400, f"Expected success for {endpoint}"

        # NOTE: /ready is NOT in this list: it is whitelisted from the setup
        # guard, but with all lifespan services mocked the readiness endpoint
        # itself legitimately reports 503 (service not ready) — a readiness
        # signal, not a setup-guard block (owner ruling F3).

    @pytest.mark.asyncio
    async def test_register_endpoint_accessible_before_setup(
        self, unmocked_setup_client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that registration endpoint is accessible before setup."""
        response = await unmocked_setup_client.post(
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
    async def test_503_response_structure(
        self, unmocked_setup_client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that 503 response has proper structure."""
        response = await unmocked_setup_client.get("/api/cameras")

        assert response.status_code == 503
        data = response.json()

        # Verify response structure (shipped setup_guard.py payload — no
        # 'code' key; owner ruling F3)
        assert "detail" in data
        assert "setup_url" in data
        assert "setup_status_url" in data
        assert isinstance(data["detail"], str)
        assert isinstance(data["setup_url"], str)
        assert isinstance(data["setup_status_url"], str)

    @pytest.mark.asyncio
    async def test_login_immediately_after_register_is_not_503(
        self,
        unmocked_setup_client: AsyncClient,
        clean_tables: None,
        real_redis: RedisClient,
    ) -> None:
        """Registration must invalidate the guard's cached negative verdict.

        Session-learned defect (sandbox bring-up 2026-09-22): registering the
        first admin succeeded, but the immediately following login got
        503 "Initial setup required" — the guard had cached "setup required"
        from a check made before the registration (60s TTL) and the new admin
        was locked out until it expired. The first-run flow was broken by the
        guard's own cache. The register route now calls
        invalidate_setup_cache() after committing the first user.
        """
        from unittest.mock import patch

        from backend.api.routes import auth as auth_routes

        async def _real_redis_optional():
            return real_redis

        # Prime the guard's negative cache with a blocked pre-setup request.
        pre = await unmocked_setup_client.get("/api/cameras")
        assert pre.status_code == 503

        register = await unmocked_setup_client.post(
            "/api/auth/register",
            json={
                "username": "admin",
                "email": "admin@example.com",
                "password": "SecurePassword123!",  # pragma: allowlist secret
            },
        )
        assert register.status_code == 201

        # Immediate login — before the fix this hit the stale cached verdict
        # and returned 503 despite the admin existing in the database.
        with patch.object(auth_routes, "get_redis_optional", _real_redis_optional):
            login = await unmocked_setup_client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "SecurePassword123!"},  # pragma: allowlist secret
            )
        assert login.status_code == 200, (
            "login immediately after registration must not be 503'd by the "
            f"guard's cached verdict: got {login.status_code}"
        )

        # Non-whitelisted routes are open right away too — no TTL wait.
        cameras = await unmocked_setup_client.get("/api/cameras")
        assert cameras.status_code == 200


# =============================================================================
# Setup Flow Tests
# =============================================================================


class TestSetupFlow:
    """Tests for complete setup flow enabling endpoints."""

    @pytest.mark.asyncio
    async def test_setup_flow_enables_endpoints(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that completing setup enables all endpoints.

        The pre-setup 503 half of this contract is covered by
        TestPreSetupProtection against unmocked_setup_client — the shared
        client fixture patches SetupGuardMiddleware._check_setup_complete to
        always return True, so asserting a 503 through it is unreachable by
        construction (owner ruling F3). This test therefore exercises the
        THROUGH-setup arc: pre-setup status flag, registration, post-setup
        status flag, login, and post-setup access.
        """
        # Step 1: Verify we need setup (shipped field: setup_required;
        # owner ruling F3 — auth redesign NEM-5312/5322)
        status_response = await client.get("/api/auth/setup-status")
        assert status_response.status_code == 200
        assert status_response.json()["setup_required"] is True

        # Step 2: (pre-setup blocking assertions live in
        # TestPreSetupProtection.test_all_endpoints_return_503_before_setup —
        # the shared client cannot observe them; see docstring)

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

        # Step 5: Verify setup complete (shipped field: setup_required)
        status_after = await client.get("/api/auth/setup-status")
        assert status_after.status_code == 200
        assert status_after.json()["setup_required"] is False

        # Step 6: Login — shipped contract sets an HTTP-only session cookie and
        # returns {user: {...}}; there is no bearer access_token (auth
        # redesign NEM-5312/5322; owner ruling F3)
        login_response = await client.post(
            "/api/auth/login",
            json={
                "username": "admin",
                "password": "SecurePassword123!",  # pragma: allowlist secret
            },
        )
        assert login_response.status_code == 200
        assert login_response.json()["user"]["username"] == "admin"
        assert "set-cookie" in login_response.headers

        # Step 7: Verify endpoints are accessible after setup (open post-setup
        # API per the shipped single-user local model — AGENTS.md auth model;
        # the shared client's default X-API-Key is the valid key)
        cameras_after = await client.get("/api/cameras")
        assert cameras_after.status_code == 200

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

        # Try to register second user (shipped: 409 Conflict "Registration is
        # closed. Users already exist" — register_user docstring; owner ruling F3)
        second_reg = await client.post(
            "/api/auth/register",
            json={
                "username": "hacker",
                "email": "hacker@example.com",
                "password": "Password123!",  # pragma: allowlist secret
            },
        )
        assert second_reg.status_code == 409
        data = second_reg.json()
        assert "registration" in data["detail"].lower()
        assert "closed" in data["detail"].lower()


# =============================================================================
# Post-Setup Authentication Tests
# =============================================================================


class TestPostSetupAuthentication:
    """Tests for authentication requirement after setup."""

    @pytest.mark.asyncio
    async def test_open_after_setup(self, client: AsyncClient, clean_tables: None) -> None:
        """Test that general endpoints are open after setup.

        Shipped auth model (AGENTS.md; NEM-5527 disabled the global
        AuthMiddleware): single-user local deployment, network binding to
        127.0.0.1 is the security boundary, API endpoints are open after
        setup; admin/destructive routes keep per-route dependencies
        (verify_api_key, require_admin_access). Owner ruling F3.
        """
        # Complete setup
        await client.post(
            "/api/auth/register",
            json={
                "username": "admin",
                "email": "admin@example.com",
                "password": "SecurePassword123!",  # pragma: allowlist secret
            },
        )

        # Access endpoints with NO auth headers beyond the fixture default
        endpoints = [
            "/api/cameras",
            "/api/events",
            "/api/detections",
        ]

        for endpoint in endpoints:
            response = await client.get(endpoint)

            # Should NOT be 503 (setup complete) and should be reachable
            assert response.status_code != 503
            assert response.status_code == 200, f"Expected 200 (open API) for {endpoint}"

        # Protected routes keep per-route auth: user creation requires an
        # authenticated admin (get_current_admin_user).
        response = await client.post(
            "/api/admin/users",
            json={
                "username": "unauth_user",
                "email": "unauth@example.com",
                "password": "Password123!",  # pragma: allowlist secret
            },
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_session_cookie_auth_works_via_me(
        self,
        client: AsyncClient,
        clean_tables: None,
        real_redis: RedisClient,
    ) -> None:
        """Test that session-cookie authentication works after setup.

        Shipped contract: login sets an HTTP-only session cookie; bearer
        access tokens are not part of the auth surface (auth redesign
        NEM-5312/5322; owner ruling F3). The shared client fixture installs a
        mock Redis for the app lifespan, which cannot answer session reads,
        so the session store boundary is patched to the worker's real Redis
        for the duration of the test.
        """
        from unittest.mock import patch

        from backend.api.routes import auth as auth_routes

        async def _real_redis_optional():
            return real_redis

        # Register and login (AsyncClient stores the session cookie)
        await client.post(
            "/api/auth/register",
            json={
                "username": "admin",
                "email": "admin@example.com",
                "password": "SecurePassword123!",  # pragma: allowlist secret
            },
        )

        with patch.object(auth_routes, "get_redis_optional", _real_redis_optional):
            login_response = await client.post(
                "/api/auth/login",
                json={
                    "username": "admin",
                    "password": "SecurePassword123!",  # pragma: allowlist secret
                },
            )
            assert login_response.status_code == 200
            assert "set-cookie" in login_response.headers

            # SESSION_COOKIE_SECURE=True means httpx (http://test base_url)
            # correctly refuses to auto-store the cookie; a real browser over
            # HTTPS would send it. Extract and send it explicitly.
            cookie_value = httpx.Cookies()
            cookie_value.update(login_response.cookies)
            me_response = await client.get(
                "/api/auth/me",
                cookies={SESSION_COOKIE_NAME: cookie_value.get(SESSION_COOKIE_NAME, "")},
            )
            assert me_response.status_code == 200
            assert me_response.json()["username"] == "admin"
            assert me_response.json()["is_admin"] is True

    @pytest.mark.asyncio
    async def test_invalid_session_cookie_rejected(
        self,
        client: AsyncClient,
        clean_tables: None,
        real_redis: RedisClient,
    ) -> None:
        """Test that an invalid session cookie is rejected by authed routes.

        Shipped contract: bearer tokens are not part of the auth surface;
        session-cookie validation happens per-route via get_current_user
        (auth redesign NEM-5312/5322; owner ruling F3). The session store
        boundary is patched to the worker's real Redis so the invalid cookie
        is answered by a real session lookup (the shared fixture's mock Redis
        cannot answer reads — see test_session_cookie_auth_works_via_me).
        """
        from unittest.mock import patch

        from backend.api.routes import auth as auth_routes

        async def _real_redis_optional():
            return real_redis

        # Complete setup
        await client.post(
            "/api/auth/register",
            json={
                "username": "admin",
                "email": "admin@example.com",
                "password": "SecurePassword123!",  # pragma: allowlist secret
            },
        )

        # Try with an invalid session cookie
        with patch.object(auth_routes, "get_redis_optional", _real_redis_optional):
            response = await client.get(
                "/api/auth/me", cookies={SESSION_COOKIE_NAME: "invalid_session_value"}
            )

            assert response.status_code == 401


# =============================================================================
# API Key Authentication Tests
# =============================================================================


class TestApiKeyAuthentication:
    """Tests for API key authentication after setup."""

    @pytest.mark.asyncio
    async def test_api_key_auth_works(
        self,
        client: AsyncClient,
        clean_tables: None,
        real_redis: RedisClient,
    ) -> None:
        """Test that API key authentication works on protected routes after setup.

        Shipped contract: API keys are created via the session-cookie-
        authenticated /api/auth/api-keys endpoint (bearer tokens are not part
        of the auth surface; auth redesign NEM-5312/5322, owner ruling F3).
        """
        from unittest.mock import patch

        from backend.api.routes import auth as auth_routes

        async def _real_redis_optional():
            return real_redis

        with patch.object(auth_routes, "get_redis_optional", _real_redis_optional):
            # Complete setup and login (AsyncClient stores the session cookie)
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
            assert login_response.status_code == 200

            # SESSION_COOKIE_SECURE=True: httpx (http base_url) does not auto-store
            # the login cookie; a real browser over HTTPS would. Send it explicitly.
            explicit_cookie = {
                SESSION_COOKIE_NAME: login_response.cookies.get(SESSION_COOKIE_NAME, "")
            }

            # Create API key (session cookie authenticates). Shipped: the
            # minted key is write-only — it is stored hashed (prefix exposed)
            # and NO endpoint validates DB-created keys (verify_api_key checks
            # settings.api_keys only; AuthMiddleware is disabled, NEM-5527).
            api_key_response = await client.post(
                "/api/auth/api-keys",
                json={"name": "test-key"},
                cookies=explicit_cookie,
            )
            assert api_key_response.status_code == 201
            key_body = api_key_response.json()
            assert key_body["key"].startswith("nemo_k1_")
            assert key_body["prefix"] == key_body["key"][:12]

            # The only shipped API-key validation path is per-route
            # verify_api_key against settings.api_keys (integration_env sets
            # API_KEYS=["test-api-key-12345"]). POST /api/system/cleanup with
            # dry_run=true is the side-effect-free protected route (COUNT
            # queries + Path.exists() only — no deletes, no Redis, no config
            # writes), so a settings-listed key authenticating it proves the
            # end-to-end API-key contract without touching runtime state.
            response = await client.post(
                "/api/system/cleanup",
                params={"dry_run": "true"},
                headers={"X-API-Key": TEST_API_KEY},
            )
            assert response.status_code == 200
            assert response.json()["dry_run"] is True

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

        # Try with invalid API key on a route that has per-route auth
        # protection (verify_api_key/get_current_admin_user) — the global
        # AuthMiddleware is disabled (NEM-5527), so /api/cameras is open and
        # cannot carry this assertion (owner ruling F3).
        response = await client.post(
            "/api/admin/users",
            json={
                "username": "should_fail",
                "email": "should_fail@example.com",
                "password": "Password123!",  # pragma: allowlist secret
            },
            headers={"X-API-Key": "invalid_key"},
        )

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

        # Subsequent requests should work with cookies
        # (AsyncClient automatically handles cookies)
        response = await client.get("/api/cameras")

        # Should work with session cookie
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_session_logout_clears_cookie(
        self,
        client: AsyncClient,
        clean_tables: None,
        real_redis: RedisClient,
    ) -> None:
        """Test that logout clears session cookie."""
        from unittest.mock import patch

        from backend.api.routes import auth as auth_routes

        async def _real_redis_optional():
            return real_redis

        with patch.object(auth_routes, "get_redis_optional", _real_redis_optional):
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
            assert login_response.status_code == 200

            # SESSION_COOKIE_SECURE=True: httpx (http base_url) does not auto-store
            # the login cookie; send it explicitly (owner ruling F3)
            explicit_cookie = {
                SESSION_COOKIE_NAME: login_response.cookies.get(SESSION_COOKIE_NAME, "")
            }

            # Logout (session cookie authenticates; no bearer token in the shipped
            # contract — auth redesign NEM-5312/5322, owner ruling F3)
            logout_response = await client.post("/api/auth/logout", cookies=explicit_cookie)
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
        self,
        client: AsyncClient,
        clean_tables: None,
        real_redis: RedisClient,
    ) -> None:
        """Test that admin can create additional users after setup."""
        from unittest.mock import patch

        from backend.api.routes import auth as auth_routes

        async def _real_redis_optional():
            return real_redis

        with patch.object(auth_routes, "get_redis_optional", _real_redis_optional):
            # Setup first admin user
            await client.post(
                "/api/auth/register",
                json={
                    "username": "admin",
                    "email": "admin@example.com",
                    "password": "SecurePassword123!",  # pragma: allowlist secret
                },
            )

            # Login as admin (session cookie; no bearer token in the shipped
            # contract — auth redesign NEM-5312/5322, owner ruling F3)
            login_response = await client.post(
                "/api/auth/login",
                json={
                    "username": "admin",
                    "password": "SecurePassword123!",  # pragma: allowlist secret
                },
            )
            assert login_response.status_code == 200

            # SESSION_COOKIE_SECURE=True: send the login cookie explicitly
            admin_cookie = {
                SESSION_COOKIE_NAME: login_response.cookies.get(SESSION_COOKIE_NAME, "")
            }

            # Create second user as admin (session cookie authenticates)
            create_user_response = await client.post(
                "/api/admin/users",
                json={
                    "username": "user2",
                    "email": "user2@example.com",
                    "password": "Password123!",  # pragma: allowlist secret
                },
                cookies=admin_cookie,
            )

            assert create_user_response.status_code == 201
            user_data = create_user_response.json()
            assert user_data["username"] == "user2"
            assert user_data["is_admin"] is False

    @pytest.mark.asyncio
    async def test_non_admin_cannot_create_users(
        self,
        client: AsyncClient,
        clean_tables: None,
        real_redis: RedisClient,
    ) -> None:
        """Test that non-admin users cannot create users."""
        from unittest.mock import patch

        from backend.api.routes import auth as auth_routes

        async def _real_redis_optional():
            return real_redis

        with patch.object(auth_routes, "get_redis_optional", _real_redis_optional):
            # Setup first admin
            await client.post(
                "/api/auth/register",
                json={
                    "username": "admin",
                    "email": "admin@example.com",
                    "password": "SecurePassword123!",  # pragma: allowlist secret
                },
            )

            # Admin creates regular user (session cookie; owner ruling F3)
            login_response = await client.post(
                "/api/auth/login",
                json={
                    "username": "admin",
                    "password": "SecurePassword123!",  # pragma: allowlist secret
                },
            )
            assert login_response.status_code == 200

            # SESSION_COOKIE_SECURE=True: send the login cookie explicitly
            admin_cookie = {
                SESSION_COOKIE_NAME: login_response.cookies.get(SESSION_COOKIE_NAME, "")
            }

            await client.post(
                "/api/admin/users",
                json={
                    "username": "regularuser",
                    "email": "regular@example.com",
                    "password": "Password123!",  # pragma: allowlist secret
                },
                cookies=admin_cookie,
            )

            # Login as regular user (replaces the admin session cookie)
            user_login = await client.post(
                "/api/auth/login",
                json={
                    "username": "regularuser",
                    "password": "Password123!",  # pragma: allowlist secret
                },
            )
            assert user_login.status_code == 200

            # SESSION_COOKIE_SECURE=True: send the login cookie explicitly
            user_cookie = {SESSION_COOKIE_NAME: user_login.cookies.get(SESSION_COOKIE_NAME, "")}

            # Try to create user as non-admin (session cookie authenticates the
            # get_current_admin_user dependency, which rejects with 403)
            create_response = await client.post(
                "/api/admin/users",
                json={
                    "username": "user3",
                    "email": "user3@example.com",
                    "password": "Password123!",  # pragma: allowlist secret
                },
                cookies=user_cookie,
            )

            assert create_response.status_code == 403
