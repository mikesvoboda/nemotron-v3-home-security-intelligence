"""Route-level unit tests for backend/api/routes/auth.py.

Lives at the canonical path-mirrored location (unit/api/routes/test_auth.py)
that scripts/check-test-coverage-gate.py's find_test_file resolves for
auth.py — the sibling convention every other route follows (test_alerts.py,
test_cameras.py, …). Auth's coverage existed (integration flows, unit/routes/
legacy draft) but not at the mirrored path, so the gate's discovery reported
"MISSING TESTS: backend/api/routes/auth.py" while real tests existed
elsewhere — a false red that blocked PR #6641's gate run.

Asserts the SHIPPED contract (session-cookie auth, NEM-5312/5322; owner
ruling F3): setup_required flag, first-admin-only registration that
invalidates the SetupGuard cache, login setting an httponly session cookie,
and login succeeding cookieless when Redis is absent. The legacy JWT-era
draft in unit/routes/test_auth_routes.py asserts a never-shipped contract;
these tests are the kept ones.

No DB or Redis: get_db is overridden with a scripted session; AuthService,
SessionService, and the setup-guard invalidation hook are patched at the
auth-routes module seam.
"""

from __future__ import annotations

import unittest.mock
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes import auth as auth_routes
from backend.api.routes.auth import SESSION_COOKIE_NAME, router
from backend.core.database import get_db

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 22, 12, 0, 0, tzinfo=UTC)


def make_user(*, username: str = "admin", is_active: bool = True) -> MagicMock:
    user = MagicMock()
    user.id = "user-1"
    user.username = username
    user.email = f"{username}@example.com"
    user.password_hash = "argon2-hash"
    user.is_active = is_active
    user.is_admin = True
    user.created_at = NOW
    user.last_login_at = None
    return user


def scripted_db(*results):
    """get_db override returning one scripted result per execute() call.

    Each result is the object scalar()/scalar_one_or_none() will be called
    on — pass the value itself; a shared MagicMock wrapper answers both
    accessor styles.
    """

    async def _override():
        session = AsyncMock()
        remaining = list(results)

        async def _execute(_stmt):
            value = remaining.pop(0) if remaining else None
            result = MagicMock()
            result.scalar.return_value = value
            result.scalar_one_or_none.return_value = value
            return result

        session.execute = _execute
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        yield session

    return _override


@pytest.fixture
def app_factory():
    def _build(*results):
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = scripted_db(*results)
        return app

    return _build


@pytest.fixture
def patched_seams():
    """Patch AuthService / SessionService / invalidate_setup_cache at the route module."""
    auth_service = MagicMock()
    auth_service.hash_password.return_value = "argon2-hash"
    auth_service.verify_password.return_value = True

    session_service = MagicMock()
    session_service.create_session = AsyncMock(return_value="session-token-1")

    invalidate = MagicMock()

    auth_service_cls = MagicMock(return_value=auth_service)
    session_service_cls = MagicMock(return_value=session_service)

    with (
        unittest.mock.patch.object(auth_routes, "AuthService", auth_service_cls),
        unittest.mock.patch.object(auth_routes, "SessionService", session_service_cls),
        unittest.mock.patch.object(auth_routes, "invalidate_setup_cache", invalidate),
    ):
        yield {
            "auth_service": auth_service,
            "session_service": session_service,
            "invalidate": invalidate,
        }


class TestSetupStatus:
    def test_setup_required_when_no_users(self, app_factory, patched_seams) -> None:
        client = TestClient(app_factory(0))
        response = client.get("/api/auth/setup-status")
        assert response.status_code == 200
        assert response.json()["setup_required"] is True

    def test_setup_complete_when_users_exist(self, app_factory, patched_seams) -> None:
        client = TestClient(app_factory(1))
        response = client.get("/api/auth/setup-status")
        assert response.status_code == 200
        assert response.json()["setup_required"] is False


class TestRegistration:
    def test_first_registration_creates_admin_and_invalidates_guard(
        self, app_factory, patched_seams
    ) -> None:
        # Scripted counts: 0 (no users yet), None (username free), None (email free)
        client = TestClient(app_factory(0, None, None))
        response = client.post(
            "/api/auth/register",
            json={
                "username": "admin",
                "email": "admin@example.com",
                "password": "SecurePassword123!",  # pragma: allowlist secret
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["is_admin"] is True
        assert data["username"] == "admin"
        # The SetupGuard's cached negative verdict must be dropped by the
        # register route — without this, the brand-new admin's immediate
        # login is 503'd until the guard's TTL expires (session-learned
        # defect, 2026-09-22 sandbox bring-up).
        patched_seams["invalidate"].assert_called_once_with()

    def test_registration_blocked_when_users_exist(self, app_factory, patched_seams) -> None:
        client = TestClient(app_factory(1))
        response = client.post(
            "/api/auth/register",
            json={
                "username": "late",
                "email": "late@example.com",
                "password": "SecurePassword123!",  # pragma: allowlist secret
            },
        )
        assert response.status_code == 409
        assert "closed" in response.json()["detail"].lower()


class TestLogin:
    def test_login_sets_session_cookie(self, app_factory, patched_seams) -> None:
        async def _redis():
            return AsyncMock()

        client = TestClient(app_factory(make_user()))
        with unittest.mock.patch.object(auth_routes, "get_redis_optional", _redis):
            response = client.post(
                "/api/auth/login",
                json={
                    "username": "admin",
                    "password": "SecurePassword123!",
                },  # pragma: allowlist secret
            )
        assert response.status_code == 200
        assert response.json()["user"]["username"] == "admin"
        assert response.cookies.get(SESSION_COOKIE_NAME) == "session-token-1"
        cookie_header = response.headers["set-cookie"]
        assert "httponly" in cookie_header.lower()
        assert "samesite=lax" in cookie_header.lower()

    def test_login_without_redis_succeeds_without_cookie(self, app_factory, patched_seams) -> None:
        """Shipped behavior: login returns 200 (no session cookie) when no
        Redis is available — SetupGuard, not the session cookie, is the gate
        in the single-user local model."""

        async def _no_redis():
            return None

        client = TestClient(app_factory(make_user()))
        with unittest.mock.patch.object(auth_routes, "get_redis_optional", _no_redis):
            response = client.post(
                "/api/auth/login",
                json={
                    "username": "admin",
                    "password": "SecurePassword123!",
                },  # pragma: allowlist secret
            )
        assert response.status_code == 200
        assert SESSION_COOKIE_NAME not in response.cookies

    def test_login_wrong_password_401(self, app_factory, patched_seams) -> None:
        patched_seams["auth_service"].verify_password.return_value = False
        client = TestClient(app_factory(make_user()))
        response = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "WrongPassword123!"},  # pragma: allowlist secret
        )
        assert response.status_code == 401

    def test_login_unknown_user_401(self, app_factory, patched_seams) -> None:
        client = TestClient(app_factory(None))  # user lookup finds nobody
        response = client.post(
            "/api/auth/login",
            json={
                "username": "ghost",
                "password": "SecurePassword123!",
            },  # pragma: allowlist secret
        )
        assert response.status_code == 401

    def test_login_inactive_account_401(self, app_factory, patched_seams) -> None:
        client = TestClient(app_factory(make_user(is_active=False)))
        response = client.post(
            "/api/auth/login",
            json={
                "username": "admin",
                "password": "SecurePassword123!",
            },  # pragma: allowlist secret
        )
        assert response.status_code == 401
        assert "disabled" in response.json()["detail"].lower()
