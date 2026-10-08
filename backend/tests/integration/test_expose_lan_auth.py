"""EXPOSE_LAN against the real session store and database (B1.5; OD-12; ISS-029).

A login issues a Redis session. With EXPOSE_LAN=true that session, or a
configured API key, opens a gated route, and nothing else does; logout closes
the session again. POST /api/notification/test records whoever authenticated
as its audit actor.

The shared ``client`` fixture sends the integration API key on every request;
these tests drop it wherever the point is a request without one.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from backend.api.middleware import auth as auth_middleware
from backend.api.routes import auth as auth_routes
from backend.api.routes.auth import SESSION_COOKIE_NAME
from backend.api.schemas.notification import NotificationChannel
from backend.core.config import get_settings
from backend.core.database import get_session
from backend.models.audit import AuditLog
from backend.services.notification import NotificationDelivery, NotificationService

if TYPE_CHECKING:
    from httpx import AsyncClient

    from backend.core.redis import RedisClient

pytestmark = pytest.mark.integration

PASSWORD = "SecurePassword123!"  # pragma: allowlist secret  # nosemgrep: hardcoded-password
TEST_API_KEY = "test-api-key-12345"  # pragma: allowlist secret — integration_env API_KEYS entry
GATED_ROUTE = "/api/cameras"


@pytest.fixture
def exposed(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("EXPOSE_LAN", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def loopback(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv("EXPOSE_LAN", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def real_session_store(real_redis: RedisClient) -> Iterator[None]:
    """Point login and the gate at the worker's real Redis.

    The shared client fixture's lifespan Redis is a mock that cannot answer
    session reads (test_auth_flow.py precedent).
    """

    async def _real_redis_optional() -> RedisClient:
        return real_redis

    with (
        patch.object(auth_routes, "get_redis_optional", _real_redis_optional),
        patch.object(auth_middleware, "get_redis_optional", _real_redis_optional),
    ):
        yield


@pytest.fixture
async def anonymous(client: AsyncClient) -> AsyncIterator[AsyncClient]:
    client.headers.pop("X-API-Key", None)
    yield client


async def _register_and_login(client: AsyncClient) -> dict[str, str]:
    """The first admin registers and logs in; return the session cookie."""
    registered = await client.post(
        "/api/auth/register",
        json={"username": "admin", "email": "admin@example.com", "password": PASSWORD},
    )
    assert registered.status_code == 201
    login = await client.post("/api/auth/login", json={"username": "admin", "password": PASSWORD})
    assert login.status_code == 200
    return {SESSION_COOKIE_NAME: login.cookies[SESSION_COOKIE_NAME]}


async def _audit_actors() -> list[str]:
    async with get_session() as session:
        rows = await session.execute(
            select(AuditLog.actor).where(AuditLog.action == "notification_test")
        )
        return list(rows.scalars())


async def _send_test_notification(client: AsyncClient, **kwargs: object) -> None:
    delivered = NotificationDelivery(
        channel=NotificationChannel.WEBHOOK, success=True, recipient="https://hooks.example.com/x"
    )
    with patch.object(NotificationService, "send_webhook", AsyncMock(return_value=delivered)):
        response = await client.post(
            "/api/notification/test",
            json={"channel": "webhook", "webhook_url": "https://hooks.example.com/x"},
            **kwargs,
        )
    assert response.status_code == 200
    assert response.json()["success"] is True


class TestExposedGate:
    async def test_login_session_opens_a_gated_route(
        self, anonymous: AsyncClient, clean_tables: None, real_session_store: None, exposed: None
    ) -> None:
        cookie = await _register_and_login(anonymous)

        assert (await anonymous.get(GATED_ROUTE)).status_code == 401
        assert (await anonymous.get(GATED_ROUTE, cookies=cookie)).status_code == 200

    async def test_logout_closes_the_session(
        self, anonymous: AsyncClient, clean_tables: None, real_session_store: None, exposed: None
    ) -> None:
        cookie = await _register_and_login(anonymous)

        assert (await anonymous.post("/api/auth/logout", cookies=cookie)).status_code == 200
        assert (await anonymous.get(GATED_ROUTE, cookies=cookie)).status_code == 401

    async def test_configured_api_key_opens_a_gated_route(
        self, anonymous: AsyncClient, clean_tables: None, exposed: None
    ) -> None:
        assert (await anonymous.get(GATED_ROUTE)).status_code == 401
        response = await anonymous.get(GATED_ROUTE, headers={"X-API-Key": TEST_API_KEY})
        assert response.status_code == 200

    async def test_setup_status_reports_auth_required(
        self, anonymous: AsyncClient, clean_tables: None, exposed: None
    ) -> None:
        response = await anonymous.get("/api/auth/setup-status")
        assert response.status_code == 200
        assert response.json() == {"setup_required": True, "auth_required": True}


class TestNotificationTestAuditActor:
    async def test_records_the_logged_in_user(
        self, anonymous: AsyncClient, clean_tables: None, real_session_store: None, exposed: None
    ) -> None:
        cookie = await _register_and_login(anonymous)

        await _send_test_notification(anonymous, cookies=cookie)

        assert await _audit_actors() == ["admin"]

    async def test_records_an_api_key_caller(
        self, client: AsyncClient, clean_tables: None, real_session_store: None
    ) -> None:
        await _send_test_notification(client)

        assert await _audit_actors() == ["api-key"]

    async def test_records_anonymous_without_a_credential_on_loopback(
        self, anonymous: AsyncClient, clean_tables: None, real_session_store: None, loopback: None
    ) -> None:
        await _send_test_notification(anonymous)

        assert await _audit_actors() == ["anonymous"]
