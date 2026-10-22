"""DB-backed tests for the outbound webhook retry worker (B4.2, ruling 310).

Needs real Postgres: the claim is an UPDATE ... WHERE id IN (SELECT ... FOR
UPDATE SKIP LOCKED) whose lease semantics cannot be faked by SQLite or mocks.
Uses the conftest's ``worker_db_url`` fixture so each pytest-xdist worker gets
its own database and cannot truncate another worker's seeds.

The binding's test list (ruling 310): a failed delivery is resent after its
backoff elapses (measured on a fixed clock), and resending stops once
``attempt_count`` reaches the webhook's ``max_retries``.

The seam is ``WebhookService._send_request`` on the worker's service instance:
the worker's claim runs as real SQL against the seeded rows and the service's
real ``resend_delivery_payload`` records the outcome — only the HTTP send is
stubbed, failing as a real ``httpx.ConnectError`` (an ``httpx.RequestError``)
so the backoff path is the production one.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch
from uuid import uuid7

import httpx
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# asyncio_mode=auto (pyproject) makes async tests run under pytest-asyncio.


@pytest_asyncio.fixture
async def db_engine(worker_db_url: str):
    engine = create_async_engine(worker_db_url, isolation_level="AUTOCOMMIT")
    from backend.models.camera import Base
    from backend.models.outbound_webhook import OutboundWebhook  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=None)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def clean_webhooks(db_engine):
    """Clear the outbound webhook tables between tests (worker DBs are per-worker)."""
    async with db_engine.begin() as conn:
        await conn.execute(text("DELETE FROM webhook_deliveries"))
        await conn.execute(text("DELETE FROM outbound_webhooks"))
    yield
    async with db_engine.begin() as conn:
        await conn.execute(text("DELETE FROM webhook_deliveries"))
        await conn.execute(text("DELETE FROM outbound_webhooks"))


async def _seed_retrying_delivery(
    session_factory: Any,
    *,
    max_retries: int = 3,
    retry_delay_seconds: int = 10,
    enabled: bool = True,
    url: str = "https://x.test/hook",
    attempts: int = 1,
    next_retry_at: datetime | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Seed one outbound webhook with one RETRYING delivery.

    The raw INSERT bypasses Python-side column defaults, so the NOT NULL
    counter columns are seeded explicitly.
    """
    wid = str(uuid7())
    did = str(uuid7())
    async with session_factory() as session:
        await session.execute(
            text(
                "INSERT INTO outbound_webhooks (id, name, url, event_types, integration_type,"
                " enabled, custom_headers, max_retries, retry_delay_seconds, created_at,"
                " updated_at, on_local_network, total_deliveries, successful_deliveries)"
                " VALUES (:id, :name, :url, :event_types, 'generic', :enabled, '{}',"
                " :max_retries, :retry_delay_seconds, timezone('utc', now()),"
                " timezone('utc', now()), FALSE, 0, 0)"
            ),
            {
                "id": wid,
                "name": f"w-{wid[:8]}",
                "url": url,
                "event_types": ["alert_fired"],
                "enabled": enabled,
                "max_retries": max_retries,
                "retry_delay_seconds": retry_delay_seconds,
            },
        )
        await session.execute(
            text(
                "INSERT INTO webhook_deliveries (id, webhook_id, event_type, status,"
                " request_payload, attempt_count, next_retry_at, created_at)"
                " VALUES (:id, :wid, 'alert_fired', 'retrying', :payload, :attempts,"
                " :next_retry_at, timezone('utc', now()))"
            ),
            {
                "id": did,
                "wid": wid,
                "payload": json.dumps(
                    payload if payload is not None else {"event_type": "alert_fired"}
                ),  # text() params bypass JSONB typing; send the wire form
                "attempts": attempts,
                "next_retry_at": next_retry_at,
            },
        )
        await session.commit()
    return {"webhook_id": wid, "delivery_id": did}


async def _row(session_factory: Any, delivery_id: str) -> Any:
    async with session_factory() as session:
        result = await session.execute(
            text(
                "SELECT status, attempt_count, next_retry_at, error_message, status_code"
                " FROM webhook_deliveries WHERE id = :id"
            ),
            {"id": delivery_id},
        )
        return result.one_or_none()


def _fixed_now() -> datetime:
    return datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC)


async def test_due_delivery_is_claimed_and_resent(session_factory, clean_webhooks) -> None:
    """A RETRYING delivery past next_retry_at is claimed (attempt incremented,
    lease stamped) and then resent to success by the same cycle."""
    from backend.services.webhook_retry_worker import WebhookRetryWorker

    seeded = await _seed_retrying_delivery(
        session_factory,
        attempts=1,
        max_retries=3,
        next_retry_at=_fixed_now() - timedelta(seconds=5),
    )
    worker = WebhookRetryWorker(session_factory)

    # Only the HTTP send is stubbed (2xx canned); the claim is real SQL and the
    # outcome is recorded by the service's real resend_delivery_payload.
    async def _ok(webhook, payload):
        return 200, "queued", 5

    with patch.object(worker._service, "_send_request", _ok):
        claimed = await worker.process_due(now=_fixed_now())
    assert claimed == 1

    row = await _row(session_factory, seeded["delivery_id"])
    # The claim incremented the attempt (1 -> 2) and leased the row; the
    # successful resend then recorded SUCCESS and cleared the retry time.
    assert row.attempt_count == 2
    assert row.status == "success"
    assert row.next_retry_at is None


async def test_failed_resend_schedules_backoff_then_success(
    session_factory, clean_webhooks
) -> None:
    """Failed delivery resent after its backoff elapses: the first resend fails
    (a new backoff is scheduled from the incremented attempt), the next resend
    succeeds and clears the retry time."""
    from backend.services.webhook_retry_worker import WebhookRetryWorker

    seeded = await _seed_retrying_delivery(
        session_factory,
        attempts=1,
        max_retries=3,
        retry_delay_seconds=10,
        next_retry_at=_fixed_now() - timedelta(seconds=1),
    )
    worker = WebhookRetryWorker(session_factory)
    calls = {"n": 0}

    async def _flaky(webhook, payload):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("resend failed")
        return 200, "queued", 5

    # Cycle 1 (fixed clock): the claim leases the row (attempt 1 -> 2) and the
    # send fails with a real httpx.RequestError — the service's normal failure
    # path reschedules RETRYING with a new backoff computed from the
    # already-incremented attempt: base_delay * 2^(attempt-1) = 10 * 2^1 =
    # 20s. The backoff is computed from utc_now(), not the worker's clock
    # argument, so the row's new retry time is asserted against a window
    # around the real now.
    with patch.object(worker._service, "_send_request", _flaky):
        await worker.process_due(now=_fixed_now())
    row = await _row(session_factory, seeded["delivery_id"])
    assert row.status == "retrying"
    assert row.attempt_count == 2
    assert row.next_retry_at is not None
    assert row.error_message == "resend failed"
    real_now = datetime.now(UTC)
    delta = row.next_retry_at - real_now
    assert timedelta(seconds=15) < delta < timedelta(seconds=25)

    # Before the backoff elapses the claim finds nothing: the row's retry time
    # holds it back, so a failed resend is not reclaimed immediately.
    assert await worker.process_due(now=row.next_retry_at - timedelta(seconds=1)) == 0

    # Cycle 2 (clock past the backoff): send succeeds -> SUCCESS, no retry time.
    async def _ok(webhook, payload):
        return 200, "queued", 5

    with patch.object(worker._service, "_send_request", _ok):
        await worker.process_due(now=row.next_retry_at + timedelta(seconds=1))
    row = await _row(session_factory, seeded["delivery_id"])
    assert row.status == "success"
    assert row.next_retry_at is None


async def test_resend_stops_at_max_retries(session_factory, clean_webhooks) -> None:
    """Once attempt_count reaches the webhook's max_retries the claim skips the
    row for good — the retry loop terminates (ruling 310's stop condition)."""
    from backend.services.webhook_retry_worker import WebhookRetryWorker

    seeded = await _seed_retrying_delivery(
        session_factory,
        attempts=3,  # already AT max_retries=3
        max_retries=3,
        next_retry_at=_fixed_now() - timedelta(seconds=1),
    )
    worker = WebhookRetryWorker(session_factory)

    async def _boom(webhook, payload):
        raise AssertionError("send must not run once max_retries is reached")

    with patch.object(worker._service, "_send_request", _boom):
        claimed = await worker.process_due(now=_fixed_now())
    assert claimed == 0

    row = await _row(session_factory, seeded["delivery_id"])
    assert row.status == "retrying"  # untouched
    assert row.attempt_count == 3  # not incremented


async def test_disabled_webhook_and_future_retry_not_claimed(
    session_factory, clean_webhooks
) -> None:
    """A disabled webhook's rows and rows whose retry time has not arrived are
    both left alone by the claim."""
    from backend.services.webhook_retry_worker import WebhookRetryWorker

    disabled = await _seed_retrying_delivery(
        session_factory, enabled=False, next_retry_at=_fixed_now() - timedelta(seconds=1)
    )
    future = await _seed_retrying_delivery(
        session_factory, next_retry_at=_fixed_now() + timedelta(hours=1)
    )
    worker = WebhookRetryWorker(session_factory)

    async def _boom(webhook, payload):
        raise AssertionError("send must not run for unclaimed rows")

    with patch.object(worker._service, "_send_request", _boom):
        assert await worker.process_due(now=_fixed_now()) == 0
    assert (await _row(session_factory, disabled["delivery_id"])).status == "retrying"
    assert (await _row(session_factory, future["delivery_id"])).status == "retrying"
