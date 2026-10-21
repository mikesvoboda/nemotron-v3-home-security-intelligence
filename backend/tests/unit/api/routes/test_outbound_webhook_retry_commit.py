"""[r285] The webhook retry must commit before it answers.

Ruling 285's amendment 6302995876: ``retry_delivery`` (backend/api/routes/outbound_webhooks.py)
takes ``Depends(get_db)`` and the session's commit lives in ``get_db``'s teardown
(backend/core/database.py). Under FastAPI's default request-scoped dependency teardown the
commit runs after the response has been sent, so a caller re-reading the delivery immediately
after a 200 sees the pre-retry row (the maui attempt-9 stale read), and a failed commit is
reported to the client as success.

Both tests run the SHIPPED ``get_db`` — the bug is in how its teardown commit interacts
with FastAPI's dependency scope, so replacing the dependency would make the instrument
blind to its own claim. Only the module-level session factory is patched, to point at a
dedicated Postgres database created for this module (same recipe as the integration
tier's per-worker databases).
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import AsyncMock
from unittest.mock import patch as mock_patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import backend.api.routes.outbound_webhooks as ow
import backend.core.database as dbmod
from backend.models.outbound_webhook import OutboundWebhook, WebhookDelivery, WebhookDeliveryStatus

pytestmark = pytest.mark.asyncio


def _base_postgres_url() -> str:
    """The module's own base URL: TEST_DATABASE_URL, else the shipped dev default."""
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL") or ""
    if not url:
        pytest.skip("no Postgres URL available for webhook retry commit tests")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _db_url_for(db_name: str, base_url: str) -> str:
    """base_url pointed at db_name."""
    prefix, _, suffix = base_url.rpartition("/")
    return f"{prefix}/{db_name}{suffix and '?' + suffix}"


@pytest.fixture(scope="module")
def retry_commit_db_url(request: pytest.FixtureRequest):
    """A dedicated database for this module, created and dropped around the module.

    Sync engine by design (same precedent as the integration tier's
    ``_ensure_worker_schema``): module-scoped fixtures cannot bind to
    pytest-asyncio's per-test event loop, so the DDL runs over psycopg2. The name is
    per-xdist-worker (``get_worker_db_name``'s recipe) so parallel workers don't race
    one shared name.
    """
    import sqlalchemy
    from xdist import get_xdist_worker_id

    base_url = _base_postgres_url()
    db_name = f"security_test_retry_commit_{get_xdist_worker_id(request)}"
    module_url = _db_url_for(db_name, base_url)

    admin = sqlalchemy.create_engine(
        base_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1),
        pool_pre_ping=True,
        isolation_level="AUTOCOMMIT",
    )
    try:
        with admin.connect() as conn:
            # db_name is this module's constant, never user input; identifiers cannot be
            # bound parameters in DDL. Same suppression as the integration conftest's DDL.
            conn.execute(
                # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
                text('DROP DATABASE IF EXISTS "' + db_name + '" WITH (FORCE)')
            )
            conn.execute(
                # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
                text('CREATE DATABASE "' + db_name + '"')
            )

        store = sqlalchemy.create_engine(
            module_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
        )
        with store.begin() as conn:
            OutboundWebhook.metadata.create_all(
                conn,
                tables=[OutboundWebhook.__table__, WebhookDelivery.__table__],
            )
        store.dispose()

        yield module_url
    finally:
        with admin.connect() as conn:
            conn.execute(
                # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
                text('DROP DATABASE IF EXISTS "' + db_name + '" WITH (FORCE)')
            )
        admin.dispose()


@pytest.fixture
async def seeded_store(retry_commit_db_url: str):
    """An engine over the module database with the failed delivery seeded."""
    store = create_async_engine(retry_commit_db_url)
    factory = async_sessionmaker(store, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        session.add(_webhook(_failed_delivery()))
        await session.commit()
    yield store
    # Leave the rows; the module database is dropped wholesale at teardown.


@pytest.fixture
def patched_get_db(monkeypatch: pytest.MonkeyPatch, seeded_store):
    """Run the shipped get_db verbatim against the seeded store; return its factory."""
    factory = async_sessionmaker(seeded_store, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(dbmod, "_async_session_factory", factory)
    monkeypatch.setattr(dbmod, "_engine", None)
    monkeypatch.setattr(dbmod, "_bound_loop_id", None)
    return factory


@pytest.fixture
def app(patched_get_db):
    """The app under test: shipped get_db, stubbed HTTP send."""
    return _app_with_mocked_send()


def _app_with_mocked_send() -> FastAPI:
    """The app with the outbound-webhooks router and _send_request stubbed to 200."""
    app = FastAPI()
    app.include_router(ow.router)

    async def override_webhook_service():
        service = ow.WebhookService()
        service._send_request = AsyncMock(return_value=(200, "OK", 100))  # type: ignore[method-assign]
        return service

    app.dependency_overrides[ow.get_webhook_service] = override_webhook_service
    return app


WEBHOOK_ID = "9b2f1c3a-0000-4000-8000-000000000001"
DELIVERY_ID = "9b2f1c3a-0000-4000-8000-000000000002"
EVENT_ID = "9b2f1c3a-0000-4000-8000-000000000003"


def _webhook(delivery: WebhookDelivery) -> OutboundWebhook:
    """An enabled webhook owning the delivery under test."""
    return OutboundWebhook(
        id=WEBHOOK_ID,
        name="ops-alerts",
        url="https://ops.example.com/hooks/1",
        event_types=["alert_fired"],
        integration_type="generic",
        enabled=True,
        deliveries=[delivery],
    )


def _failed_delivery() -> WebhookDelivery:
    """A failed delivery, one prior attempt, no retry pending."""
    return WebhookDelivery(
        id=DELIVERY_ID,
        webhook_id=WEBHOOK_ID,
        event_type="alert_fired",
        event_id=EVENT_ID,
        status=WebhookDeliveryStatus.FAILED,
        status_code=500,
        error_message="HTTP 500",
        attempt_count=1,
    )


async def _read_delivery(store: Any) -> WebhookDelivery:
    """A fresh-session read of the delivery under test, as the maui caller did."""
    factory = async_sessionmaker(store, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        result = await session.execute(
            select(WebhookDelivery).where(WebhookDelivery.id == DELIVERY_ID)
        )
        return result.scalar_one()


class _OrderMiddleware:
    """Appends 'response.start' to a shared list when the response head is sent."""

    def __init__(self, app: Any, order: list[str]) -> None:
        self.app = app
        self.order = order

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        async def send_recorder(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                self.order.append("response.start")
            await send(message)

        await self.app(scope, receive, send_recorder)


async def test_retry_delivery_commits_before_the_response_is_sent(
    app: FastAPI, seeded_store: Any
) -> None:
    """The 200's attempt_count must already be committed when the client re-reads it.

    Red at the ready head: with request-scoped teardown, get_db's commit runs after the
    response is sent, so a fresh session sees the pre-retry row (attempt_count 1, FAILED)
    although the 200 answered attempt_count 2, SUCCESS — the maui attempt-9 stale read.
    """
    order: list[str] = []
    original_commit = AsyncSession.commit

    async def recording_commit(self: AsyncSession) -> None:
        order.append("commit")
        await original_commit(self)

    with mock_patch.object(AsyncSession, "commit", recording_commit):
        async with AsyncClient(
            transport=ASGITransport(app=_OrderMiddleware(app, order)), base_url="http://test"
        ) as client:
            response = await client.post(f"/api/outbound-webhooks/deliveries/{DELIVERY_ID}/retry")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "success"
    assert response.json()["attempt_count"] == 2

    # The stale read: a fresh session must see the committed retry state.
    row = await _read_delivery(seeded_store)
    assert row.status == WebhookDeliveryStatus.SUCCESS
    assert row.attempt_count == 2

    # The ordering pin: the commit happened before the response was sent.
    assert order.index("commit") < order.index("response.start"), order


async def test_retry_delivery_commit_failure_is_not_reported_as_success(
    app: FastAPI, seeded_store: Any
) -> None:
    """A failed commit must not answer 200 with the retry's new state.

    Red at the ready head: the handler returns the in-memory delivery (SUCCESS,
    attempt_count 2), the 200 is sent, and the teardown commit then fails — the client
    was told success for a write that never persisted.
    """

    async def failing_commit(self: AsyncSession) -> None:
        raise RuntimeError("commit failed on teardown")

    with mock_patch.object(AsyncSession, "commit", failing_commit):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(f"/api/outbound-webhooks/deliveries/{DELIVERY_ID}/retry")

    # The write never persisted; the endpoint must not answer 200 success.
    assert response.status_code >= 500, (response.status_code, response.text)

    # And the stored row must be untouched.
    row = await _read_delivery(seeded_store)
    assert row.status == WebhookDeliveryStatus.FAILED
    assert row.attempt_count == 1
