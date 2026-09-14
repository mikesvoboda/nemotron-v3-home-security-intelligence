"""Integration tests for the authentication flow.

Rewritten (R-T7-AUTHFLOW) from the original TDD-RED draft, which asserted a
never-shipped JWT contract: access/refresh token pairs, POST /api/auth/refresh,
login-by-email, multi-user registration, and Bearer-authorization on business
routes. None of that exists in the shipped surface.

Shipped contract (auth redesign NEM-5312/5322; owner ruling F3; same ground
truth as test_api_protection.py):
- Registration is first-admin-only: once a user exists, POST /register is 409.
  Username/email collisions on an empty system answer 400, not 409.
- Login takes username (required) + password and returns {user, message};
  the session token is set as an httponly session cookie — no bearer tokens
  anywhere in the response or accepted in requests.
- There is NO /api/auth/refresh endpoint. Session lifecycle is
  login → cookie → logout (or 24h TTL).
- /api/auth/me and the API-key CRUD require the session cookie via
  get_current_user / get_current_admin_user; the global AuthMiddleware is
  disabled (NEM-5527), so business routes like /api/cameras are open and
  cannot carry auth assertions. The only X-API-Key surface is per-route
  verify_api_key against settings.api_keys (integration_env sets
  API_KEYS=["test-api-key-12345"]); POST /api/system/cleanup?dry_run=true is
  the side-effect-free protected route used to prove it.

SESSION_COOKIE_SECURE=True means httpx (http://test base_url) does not
auto-store or auto-send the session cookie; tests extract it from the login
response and pass it explicitly, mirroring a browser over HTTPS. The shared
client fixture installs a mock Redis for the app lifespan that cannot answer
session reads, so session-store round-trips patch the auth route seam to the
worker's real Redis (real_redis fixture), per test_api_protection precedent.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from backend.api.routes.auth import SESSION_COOKIE_NAME

if TYPE_CHECKING:
    from httpx import AsyncClient

    from backend.core.redis import RedisClient

# Mark as integration tests
pytestmark = pytest.mark.integration

PASSWORD = "SecurePassword123!"  # pragma: allowlist secret
TEST_API_KEY = "test-api-key-12345"  # pragma: allowlist secret — integration_env API_KEYS entry


@pytest.fixture
def real_session_store(real_redis: RedisClient):
    """Patch the auth routes' Redis seam to the worker's real session store.

    The shared client fixture's mock lifespan Redis cannot answer session
    reads, so login-issued cookies would never validate without this.
    """
    from backend.api.routes import auth as auth_routes

    async def _real_redis_optional():
        return real_redis

    with patch.object(auth_routes, "get_redis_optional", _real_redis_optional):
        yield


async def _register_first_admin(client: AsyncClient, username: str = "admin") -> dict:
    """Register the first admin (shipped: first-admin-only registration)."""
    response = await client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 201
    await asyncio.sleep(1.5)  # intentional - settings cache refresh (api_protection precedent)
    return response.json()


async def _login(client: AsyncClient, username: str = "admin") -> tuple:
    """Login and return (response, session_cookie_dict).

    With the real session store patched in, login sets the session cookie;
    secure-cookie semantics mean we hand it back explicitly.
    """
    response = await client.post(
        "/api/auth/login", json={"username": username, "password": PASSWORD}
    )
    cookie = {SESSION_COOKIE_NAME: response.cookies.get(SESSION_COOKIE_NAME, "")}
    return response, cookie


# =============================================================================
# User Registration Tests
# =============================================================================


class TestUserRegistration:
    """Tests for the first-admin registration flow."""

    @pytest.mark.asyncio
    async def test_user_registration_creates_user(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """First registration creates the admin user without leaking secrets."""
        data = await _register_first_admin(client, username="newuser")

        assert data["username"] == "newuser"
        assert data["email"] == "newuser@example.com"
        assert data["id"]
        assert data["is_admin"] is True  # first user is always admin
        assert "password" not in data
        assert "password_hash" not in data

        # Setup is complete once a user exists
        status_response = await client.get("/api/auth/setup-status")
        assert status_response.status_code == 200
        assert status_response.json()["setup_required"] is False

    @pytest.mark.asyncio
    async def test_registration_blocked_when_users_exist(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Shipped contract: registration is first-admin-only — 409 once a user exists."""
        await _register_first_admin(client, username="firstadmin")

        # Even a different username/email cannot register a second account
        response = await client.post(
            "/api/auth/register",
            json={"username": "second", "email": "second@example.com", "password": PASSWORD},
        )
        assert response.status_code == 409
        assert "registration is closed" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_user_registration_weak_password(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Weak passwords are rejected by schema validation."""
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "weak",
            },  # pragma: allowlist secret
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_user_registration_invalid_email(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Invalid email format is rejected by schema validation."""
        response = await client.post(
            "/api/auth/register",
            json={"username": "testuser", "email": "not_an_email", "password": PASSWORD},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_user_registration_empty_fields(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Empty required fields are rejected."""
        response = await client.post(
            "/api/auth/register",
            json={"username": "", "email": "", "password": ""},
        )
        assert response.status_code == 422


# =============================================================================
# User Login Tests
# =============================================================================


class TestUserLogin:
    """Tests for the username/password → session-cookie login flow."""

    @pytest.mark.asyncio
    async def test_user_login_sets_session_cookie(
        self, client: AsyncClient, clean_tables: None, real_session_store: None
    ) -> None:
        """Successful login returns user info and sets the session cookie.

        Pins the negative half too: the JWT-era keys are NOT part of the
        shipped response (auth redesign NEM-5312/5322; owner ruling F3).
        """
        await _register_first_admin(client)

        response, cookie = await _login(client)

        assert response.status_code == 200
        data = response.json()
        assert data["user"]["username"] == "admin"
        assert data["user"]["is_admin"] is True
        assert data["message"]
        assert cookie[SESSION_COOKIE_NAME], "login must set the session cookie"
        assert "access_token" not in data
        assert "refresh_token" not in data
        assert "token_type" not in data

    @pytest.mark.asyncio
    async def test_user_login_wrong_password_fails(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Login with the wrong password is 401."""
        await _register_first_admin(client)

        response = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "WrongPassword123!"},  # pragma: allowlist secret
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_user_login_nonexistent_user(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Login for an unknown username is 401."""
        response = await client.post(
            "/api/auth/login", json={"username": "nonexistent", "password": PASSWORD}
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_user_login_requires_username(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """The shipped UserLoginRequest requires `username`; email-only login
        is not a supported contract (the original TDD draft asserted it)."""
        await _register_first_admin(client)

        response = await client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": PASSWORD},
        )
        assert response.status_code == 422  # username is a required field

    @pytest.mark.asyncio
    async def test_inactive_account_rejected(
        self,
        client: AsyncClient,
        clean_tables: None,
        real_session_store: None,
        db_session,
    ) -> None:
        """A disabled account cannot use an existing session."""
        from sqlalchemy import select

        from backend.models.user import User

        await _register_first_admin(client)
        response, cookie = await _login(client)
        assert response.status_code == 200

        user = (await db_session.execute(select(User).where(User.username == "admin"))).scalar_one()
        user.is_active = False
        await db_session.commit()

        me_response = await client.get("/api/auth/me", cookies=cookie)
        assert me_response.status_code == 401
        assert "disabled" in me_response.json()["detail"].lower()


# =============================================================================
# Session Management Tests (replaces the never-shipped token-refresh class)
# =============================================================================


class TestSessionManagement:
    """Tests for the session-cookie lifecycle (there is no token refresh)."""

    @pytest.mark.asyncio
    async def test_session_cookie_authenticates_me(
        self, client: AsyncClient, clean_tables: None, real_session_store: None
    ) -> None:
        """The login session cookie authenticates /api/auth/me."""
        await _register_first_admin(client)
        response, cookie = await _login(client)
        assert response.status_code == 200

        me_response = await client.get("/api/auth/me", cookies=cookie)
        assert me_response.status_code == 200
        assert me_response.json()["username"] == "admin"
        assert me_response.json()["is_admin"] is True

    @pytest.mark.asyncio
    async def test_me_without_session_rejected(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """No session cookie → 401 (session-only surface; X-API-Key does not
        authenticate cookie-scoped routes either)."""
        response = await client.get("/api/auth/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_session_cookie_rejected(
        self, client: AsyncClient, clean_tables: None, real_session_store: None
    ) -> None:
        """A cookie value with no backing session is 401."""
        response = await client.get(
            "/api/auth/me", cookies={SESSION_COOKIE_NAME: "invalid_session_value"}
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_bearer_header_not_authenticated(
        self, client: AsyncClient, clean_tables: None, real_session_store: None
    ) -> None:
        """Bearer Authorization is ignored by the cookie-only auth surface."""
        response = await client.get(
            "/api/auth/me", headers={"Authorization": "Bearer some.jwt.like.token"}
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_no_refresh_endpoint(self, client: AsyncClient, clean_tables: None) -> None:
        """POST /api/auth/refresh does not exist in the shipped surface."""
        await _register_first_admin(client)

        response = await client.post("/api/auth/refresh", json={"refresh_token": "anything"})
        assert response.status_code == 404


# =============================================================================
# API Key Tests (admin-scoped, session-cookie authenticated)
# =============================================================================


class TestAPIKeyAuthentication:
    """Tests for API key CRUD and the per-route verify_api_key surface."""

    @pytest.mark.asyncio
    async def test_api_key_creation(
        self, client: AsyncClient, clean_tables: None, real_session_store: None
    ) -> None:
        """Admin session cookie can create an API key; full key returned once."""
        await _register_first_admin(client)
        _, cookie = await _login(client)

        response = await client.post(
            "/api/auth/api-keys", json={"name": "Test API Key"}, cookies=cookie
        )

        assert response.status_code == 201
        data = response.json()
        assert data["key"].startswith("nemo_k1_")
        assert data["prefix"] == data["key"][:12]
        assert data["name"] == "Test API Key"
        assert data["id"]

    @pytest.mark.asyncio
    async def test_api_key_endpoints_require_admin_session(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """The X-API-Key header does NOT authenticate admin key CRUD —
        get_current_admin_user reads the session cookie only."""
        response = await client.get("/api/auth/api-keys")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_settings_key_authenticates_protected_route(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """The shipped X-API-Key surface authenticates settings-listed keys.

        verify_api_key (system.py/dlq.py) validates against settings.api_keys
        only — integration_env sets API_KEYS=["test-api-key-12345"].
        POST /api/system/cleanup?dry_run=true is the side-effect-free
        protected route (api_protection precedent).
        """
        response = await client.post(
            "/api/system/cleanup",
            params={"dry_run": "true"},
            headers={"X-API-Key": TEST_API_KEY},
        )
        assert response.status_code == 200
        assert response.json()["dry_run"] is True

    @pytest.mark.asyncio
    async def test_db_created_key_does_not_authenticate(
        self, client: AsyncClient, clean_tables: None, real_session_store: None
    ) -> None:
        """Pins a shipped gap: keys created via /api/auth/api-keys are stored
        in the api_keys table, but NO shipped auth path reads that table —
        every verify_api_key implementation validates settings.api_keys only
        (system.py:272, dlq.py:41; the global AuthMiddleware is disabled,
        NEM-5527; inbound_webhooks.py carries the "TODO: validate against
        stored API keys in database" admission). A DB-created key therefore
        authenticates nothing today (owner-ruling candidate, ledger
        R-T7-APIKEY-DEAD).
        """
        await _register_first_admin(client)
        _, cookie = await _login(client)

        key_response = await client.post(
            "/api/auth/api-keys", json={"name": "Auth Key"}, cookies=cookie
        )
        assert key_response.status_code == 201
        db_key = key_response.json()["key"]

        response = await client.post(
            "/api/system/cleanup",
            params={"dry_run": "true"},
            headers={"X-API-Key": db_key},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_api_key_invalid(self, client: AsyncClient, clean_tables: None) -> None:
        """A key not in settings.api_keys is rejected with 401."""
        response = await client.post(
            "/api/system/cleanup",
            params={"dry_run": "true"},
            headers={"X-API-Key": "nemo_k1_totally_invalid_key"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_api_key_list_user_keys(
        self, client: AsyncClient, clean_tables: None, real_session_store: None
    ) -> None:
        """Listing returns {items, total} with prefixes only — no plaintext keys."""
        await _register_first_admin(client)
        _, cookie = await _login(client)

        for name in ("Key 1", "Key 2"):
            created = await client.post("/api/auth/api-keys", json={"name": name}, cookies=cookie)
            assert created.status_code == 201

        response = await client.get("/api/auth/api-keys", cookies=cookie)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        for key in data["items"]:
            assert "key" not in key  # plaintext never returned post-creation
            assert "prefix" in key
            assert "name" in key

    @pytest.mark.asyncio
    async def test_api_key_revoke(
        self, client: AsyncClient, clean_tables: None, real_session_store: None
    ) -> None:
        """Revoking deactivates the key record (audit-preserving, not deletion).

        State, not authentication, is the observable here — a DB-created key
        does not authenticate any route today (test_db_created_key_does_not_
        authenticate), so "key stops working" is asserted via the list flag.
        """
        await _register_first_admin(client)
        _, cookie = await _login(client)

        key_response = await client.post(
            "/api/auth/api-keys", json={"name": "To Revoke"}, cookies=cookie
        )
        key_id = key_response.json()["id"]

        # Revoke (shipped contract: 200 + message, not 204)
        revoke_response = await client.delete(f"/api/auth/api-keys/{key_id}", cookies=cookie)
        assert revoke_response.status_code == 200
        assert "revoked" in revoke_response.json()["message"].lower()

        # Key record survives (audit trail) but is deactivated
        list_response = await client.get("/api/auth/api-keys", cookies=cookie)
        items = list_response.json()["items"]
        revoked = next(item for item in items if item["id"] == key_id)
        assert revoked["is_active"] is False

    @pytest.mark.asyncio
    async def test_api_key_revoke_unknown_404(
        self, client: AsyncClient, clean_tables: None, real_session_store: None
    ) -> None:
        """Revoking an unknown key id is 404."""
        await _register_first_admin(client)
        _, cookie = await _login(client)

        response = await client.delete("/api/auth/api-keys/does-not-exist", cookies=cookie)
        assert response.status_code == 404


# =============================================================================
# Logout and Session Management Tests
# =============================================================================


class TestLogoutAndSessions:
    """Tests for logout and multi-session behavior."""

    @pytest.mark.asyncio
    async def test_user_logout_invalidates_session(
        self, client: AsyncClient, clean_tables: None, real_session_store: None
    ) -> None:
        """Logout deletes the backing session; the old cookie stops working."""
        await _register_first_admin(client)
        _, cookie = await _login(client)

        # Session live before logout
        assert (await client.get("/api/auth/me", cookies=cookie)).status_code == 200

        logout_response = await client.post("/api/auth/logout", cookies=cookie)
        assert logout_response.status_code == 200
        assert "logged out" in logout_response.json()["message"].lower()

        # Same cookie now references a deleted session → 401
        me_response = await client.get("/api/auth/me", cookies=cookie)
        assert me_response.status_code == 401

    @pytest.mark.asyncio
    async def test_user_can_have_multiple_sessions(
        self, client: AsyncClient, clean_tables: None, real_session_store: None
    ) -> None:
        """Each login mints an independent session cookie; both stay valid."""
        await _register_first_admin(client)

        response1, cookie1 = await _login(client)
        response2, cookie2 = await _login(client)
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert cookie1[SESSION_COOKIE_NAME] != cookie2[SESSION_COOKIE_NAME]

        assert (await client.get("/api/auth/me", cookies=cookie1)).status_code == 200
        assert (await client.get("/api/auth/me", cookies=cookie2)).status_code == 200

    @pytest.mark.asyncio
    async def test_logout_without_session_is_idempotent(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Logout with no session cookie still succeeds (clears nothing)."""
        response = await client.post("/api/auth/logout")
        assert response.status_code == 200
