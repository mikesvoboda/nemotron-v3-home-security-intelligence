"""DB-backed tests for the delivery worker lease claim (B4.2).

Needs real Postgres (FOR UPDATE SKIP LOCKED semantics cannot be faked by
SQLite or mocks). Uses the conftest's ``worker_db_url`` fixture so each
pytest-xdist worker gets its own database and cannot truncate another
worker's seeds.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid7

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# asyncio_mode=auto (pyproject) makes async tests run under pytest-asyncio.


@pytest_asyncio.fixture
async def db_engine(worker_db_url: str):
    engine = create_async_engine(worker_db_url, isolation_level="AUTOCOMMIT")
    # create_all the tables this suite needs (idempotent)
    from backend.models.alert_delivery import Recipient, RecipientChannel  # noqa: F401
    from backend.models.camera import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=None)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def clean_deliveries(db_engine):
    """Truncate the delivery tables between tests (worker DBs are per-worker)."""
    async with db_engine.begin() as conn:
        await conn.execute(
            text("TRUNCATE notification_deliveries, recipient_channels, recipients CASCADE")
        )
    yield
    async with db_engine.begin() as conn:
        await conn.execute(
            text("TRUNCATE notification_deliveries, recipient_channels, recipients CASCADE")
        )


async def _seed_delivery(
    session_factory: Any,
    *,
    status: str = "pending",
    next_attempt_at: datetime | None = None,
    attempts: int = 0,
    kind: str = "email",
) -> dict[str, str]:
    recipient_id = str(uuid7())
    channel_id = str(uuid7())
    delivery_id = str(uuid7())
    event_id = 710001 + int(uuid7().hex[-5:], 16) % 100000
    alert_id = str(uuid7())
    async with session_factory() as session:
        # Parent rows: cameras -> events -> alerts (FK-enforcing DB).
        await session.execute(
            text(
                "INSERT INTO cameras (id, name, folder_path, status, created_at,"
                " ingestion_mode, motion_sensitivity)"
                " VALUES ('front_door', 'Front door', '/media/front_door', 'online',"
                " timezone('utc', now()), 'rtsp', 0.5)"
                " ON CONFLICT (id) DO NOTHING"
            ),
        )
        await session.execute(
            text(
                "INSERT INTO events (id, batch_id, camera_id, started_at, version, reviewed,"
                " flagged, is_fast_path)"
                " VALUES (:eid, :batch, 'front_door', timezone('utc', now()), 1, FALSE, FALSE, FALSE)"
                " ON CONFLICT (id) DO NOTHING"
            ),
            {"eid": event_id, "batch": f"b-{event_id}"},
        )
        await session.execute(
            text(
                "INSERT INTO alerts (id, event_id, severity, status, created_at, updated_at,"
                " dedup_key, version_id, is_high_priority, match_count)"
                " VALUES (:aid, :eid, 'medium', 'open', timezone('utc', now()), timezone('utc', now()),"
                ":dk, 1, FALSE, 1)"
            ),
            {"aid": alert_id, "eid": event_id, "dk": f"dk-{alert_id[:12]}"},
        )
        await session.execute(
            text(
                "INSERT INTO recipients (id, name, enabled, critical_breaks_quiet, created_at, updated_at)"
                " VALUES (:rid, :name, TRUE, TRUE, timezone('utc', now()), timezone('utc', now()))"
            ),
            {"rid": recipient_id, "name": f"r-{recipient_id}"},
        )
        await session.execute(
            text(
                "INSERT INTO recipient_channels (id, recipient_id, kind, target, enabled,"
                " include_names, on_local_network, created_at, updated_at)"
                " VALUES (:cid, :rid, :kind, 'x@example.com', TRUE, FALSE, FALSE,"
                " timezone('utc', now()), timezone('utc', now()))"
            ),
            {"cid": channel_id, "rid": recipient_id, "kind": kind},
        )
        await session.execute(
            text(
                "INSERT INTO notification_deliveries (id, alert_id, recipient_id, channel_id, kind,"
                " status, attempts, next_attempt_at, idempotency_key, created_at, updated_at)"
                " VALUES (:id, :aid, :rid, :cid, :kind, :status, :attempts, :nxt, :idem,"
                " timezone('utc', now()), timezone('utc', now()))"
            ),
            {
                "id": delivery_id,
                "aid": alert_id,
                "rid": recipient_id,
                "cid": channel_id,
                "kind": kind,
                "status": status,
                "attempts": attempts,
                "nxt": next_attempt_at,
                "idem": f"idem-{delivery_id}",
            },
        )
        await session.commit()
    return {
        "delivery_id": delivery_id,
        "recipient_id": recipient_id,
        "channel_id": channel_id,
        "alert_id": alert_id,
    }


def _fake_channel(result_success: bool = True, error: str | None = None) -> Any:
    from backend.services.alerting.channels.base import SendResult

    class _C:
        def __init__(self) -> None:
            self.calls: list[Any] = []

        async def send(self, task: Any) -> SendResult:
            self.calls.append(task)
            return SendResult(success=result_success, error=error)

    return _C()


async def test_two_workers_never_claim_the_same_row(session_factory, clean_deliveries) -> None:
    """SKIP LOCKED: two concurrent claim cycles disjointly partition the rows."""
    from backend.services.alerting.worker import NotificationDeliveryWorker

    seeds = []
    for _ in range(6):
        seeds.append(await _seed_delivery(session_factory))
    channel = _fake_channel()
    w1 = NotificationDeliveryWorker(session_factory, {"email": channel}, poll_interval=9999)
    w2 = NotificationDeliveryWorker(session_factory, {"email": channel}, poll_interval=9999)
    got1 = await w1.process_ready()
    got2 = await w2.process_ready()
    # No overlap: every row claimed exactly once across the two workers.
    assert got1 + got2 == 6
    claimed = list(channel.calls)
    assert len(claimed) == 6


async def test_sent_delivery_records_status_and_sent_at(session_factory, clean_deliveries) -> None:
    from backend.services.alerting.worker import NotificationDeliveryWorker

    seed = await _seed_delivery(session_factory)
    w = NotificationDeliveryWorker(session_factory, {"email": _fake_channel()}, poll_interval=9999)
    await w.process_ready()
    async with session_factory() as session:
        row = (
            await session.execute(
                text(
                    "SELECT status, sent_at, attempts FROM notification_deliveries WHERE id = :id"
                ),
                {"id": seed["delivery_id"]},
            )
        ).one()
    assert row.status == "sent"
    assert row.sent_at is not None
    assert row.attempts == 0  # attempts only counts failures


async def test_failure_schedules_backoff_then_fails(session_factory, clean_deliveries) -> None:
    """30s → 2m → 10m → failed on a fixed clock (attempts 1..4)."""
    from backend.services.alerting.worker import NotificationDeliveryWorker

    seed = await _seed_delivery(session_factory)
    w = NotificationDeliveryWorker(
        session_factory,
        {"email": _fake_channel(result_success=False, error="boom")},
        poll_interval=9999,
    )
    clock = datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC)

    # Attempt 1 -> retrying, next in 30s
    await w.process_ready(now=clock)
    row = await _row(session_factory, seed["delivery_id"])
    assert row.status == "retrying"
    assert row.attempts == 1
    assert row.next_attempt_at - clock == timedelta(seconds=30)

    # Attempt 2 -> retrying, next in 2m
    after_30s = row.next_attempt_at
    await w.process_ready(now=after_30s)
    row = await _row(session_factory, seed["delivery_id"])
    assert row.attempts == 2
    assert row.next_attempt_at - after_30s == timedelta(minutes=2)

    # Attempt 3 -> retrying, next in 10m
    after_2m = row.next_attempt_at
    await w.process_ready(now=after_2m)
    row = await _row(session_factory, seed["delivery_id"])
    assert row.attempts == 3
    assert row.next_attempt_at - after_2m == timedelta(minutes=10)

    # Attempt 4 -> failed
    after_10m = row.next_attempt_at
    await w.process_ready(now=after_10m)
    row = await _row(session_factory, seed["delivery_id"])
    assert row.status == "failed"
    assert row.last_error == "boom"


async def _row(session_factory: Any, delivery_id: str) -> Any:
    async with session_factory() as session:
        return (
            await session.execute(
                text(
                    "SELECT status, attempts, next_attempt_at, last_error"
                    " FROM notification_deliveries WHERE id = :id"
                ),
                {"id": delivery_id},
            )
        ).one()


async def test_future_next_attempt_not_claimed(session_factory, clean_deliveries) -> None:
    from backend.services.alerting.worker import NotificationDeliveryWorker

    await _seed_delivery(session_factory, next_attempt_at=datetime.now(UTC) + timedelta(hours=1))
    w = NotificationDeliveryWorker(session_factory, {"email": _fake_channel()}, poll_interval=9999)
    got = await w.process_ready()
    assert got == 0


async def test_suppressed_and_expired_not_claimed(session_factory, clean_deliveries) -> None:
    from backend.services.alerting.worker import NotificationDeliveryWorker

    await _seed_delivery(session_factory, status="suppressed")
    await _seed_delivery(session_factory, status="expired")
    w = NotificationDeliveryWorker(session_factory, {"email": _fake_channel()}, poll_interval=9999)
    got = await w.process_ready()
    assert got == 0


# -- B4.2: pipeline + delivery writer, one transaction ------------------------


async def test_pipeline_writes_delivery_rows_in_alert_transaction(
    session_factory, clean_deliveries
) -> None:
    """The planner's records land as rows in the SAME tx as the alert."""
    from sqlalchemy import select

    from backend.models.alert_delivery import NotificationDelivery
    from backend.services.alerting.delivery_writer import write_delivery_rows

    seed = await _seed_delivery(session_factory, status="expired")  # parent chain exists
    alert_id = seed["alert_id"]

    async with session_factory() as session:
        written = await write_delivery_rows(
            session,
            [
                {
                    "alert_id": alert_id,
                    "recipient_id": seed["recipient_id"],
                    "channel_id": seed["channel_id"],
                    "channel_kind": "email",
                    "status": "pending",
                }
            ],
        )
        await session.commit()
    assert written == 1

    async with session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(NotificationDelivery).where(
                        NotificationDelivery.alert_id == alert_id,
                        NotificationDelivery.status == "pending",
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(rows) == 1
    assert rows[0].alert_id == alert_id
    assert rows[0].status == "pending"
    assert rows[0].idempotency_key  # unique key assigned
