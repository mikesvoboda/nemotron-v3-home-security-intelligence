"""DB-backed tests for the pipeline's delivery-row writer (B4.2).

``write_delivery_rows`` runs inside the alert's transaction — no commit inside.
The contract the package pins ("the alert and its pending deliveries are
written in one transaction") is only provable against a real transactional
engine: the happy path commits and the rows read back; a rollback removes them
with the alert; distinct channels get distinct unique idempotency keys. Needs
real Postgres; uses the conftest's ``worker_db_url`` fixture so each
pytest-xdist worker gets its own database and cannot truncate another worker's
seeds.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid7

import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models.alert_delivery import (
    DeliveryChannelKind,
    DeliveryStatus,
    NotificationDelivery,
)
from backend.services.alerting.delivery_writer import write_delivery_rows
from backend.services.alerting.planner import PlannedDelivery

# asyncio_mode=auto (pyproject) makes async tests run under pytest-asyncio.


@pytest_asyncio.fixture
async def db_engine(worker_db_url: str):
    engine = create_async_engine(worker_db_url)  # default isolation: transactions work
    # create_all the tables this suite needs (idempotent)
    from backend.models.camera import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=None)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def clean_tables(db_engine):
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


async def _seed_parents(session_factory: Any) -> dict[str, str]:
    """Camera -> event -> alert plus one recipient + email channel; returns ids."""
    recipient_id = str(uuid7())
    channel_id = str(uuid7())
    alert_id = str(uuid7())
    event_id = 740000 + int(uuid7().hex[-5:], 16) % 100000
    async with session_factory() as session:
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
                " VALUES (:eid, :batch, 'front_door', timezone('utc', now()), 1, FALSE,"
                " FALSE, FALSE)"
                " ON CONFLICT (id) DO NOTHING"
            ),
            {"eid": event_id, "batch": f"b-{event_id}"},
        )
        await session.execute(
            text(
                "INSERT INTO alerts (id, event_id, severity, status, created_at, updated_at,"
                " dedup_key, version_id, is_high_priority, match_count)"
                " VALUES (:aid, :eid, 'medium', 'open', timezone('utc', now()),"
                " timezone('utc', now()), :dk, 1, FALSE, 1)"
            ),
            {"aid": alert_id, "eid": event_id, "dk": f"dk-{alert_id[:12]}"},
        )
        await session.execute(
            text(
                "INSERT INTO recipients (id, name, enabled, critical_breaks_quiet,"
                " created_at, updated_at)"
                " VALUES (:rid, :name, TRUE, TRUE, timezone('utc', now()),"
                " timezone('utc', now()))"
            ),
            {"rid": recipient_id, "name": f"r-{recipient_id}"},
        )
        await session.execute(
            text(
                "INSERT INTO recipient_channels (id, recipient_id, kind, target, enabled,"
                " include_names, on_local_network, created_at, updated_at)"
                " VALUES (:cid, :rid, 'email', 'x@example.com', TRUE, FALSE, FALSE,"
                " timezone('utc', now()), timezone('utc', now()))"
            ),
            {"cid": channel_id, "rid": recipient_id},
        )
        await session.commit()
    return {
        "alert_id": alert_id,
        "recipient_id": recipient_id,
        "channel_id": channel_id,
    }


def _planned(ids: dict[str, str]) -> PlannedDelivery:
    return PlannedDelivery(
        alert_id=ids["alert_id"],
        recipient_id=ids["recipient_id"],
        channel_id=ids["channel_id"],
        channel_kind=DeliveryChannelKind.EMAIL,
        status=DeliveryStatus.PENDING,
        include_names=False,
    )


class TestDeliveryWriterRows:
    async def test_rows_land_and_read_back(self, session_factory, clean_tables) -> None:
        ids = await _seed_parents(session_factory)
        async with session_factory() as session:
            written = await write_delivery_rows(session, [_planned(ids)])
            await session.commit()
        assert written == 1
        async with session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(NotificationDelivery).where(
                            NotificationDelivery.alert_id == ids["alert_id"]
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert len(rows) == 1
            row = rows[0]
            assert row.kind == "email"
            assert row.status is DeliveryStatus.PENDING
            assert row.attempts == 0
            # The idempotency key names the alert + channel + planning second.
            assert row.idempotency_key.startswith(ids["alert_id"])

    async def test_rows_vanish_when_the_alert_transaction_rolls_back(
        self, session_factory, clean_tables
    ) -> None:
        ids = await _seed_parents(session_factory)
        async with session_factory() as session:
            await write_delivery_rows(session, [_planned(ids)])
            # The pipeline's contract: no commit here — the caller's rollback
            # removes the delivery rows together with the alert.
            await session.rollback()
        async with session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(NotificationDelivery).where(
                            NotificationDelivery.alert_id == ids["alert_id"]
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert rows == []

    async def test_idempotency_keys_are_unique_per_row(self, session_factory, clean_tables) -> None:
        ids = await _seed_parents(session_factory)
        second = dict(ids)
        second["channel_id"] = str(uuid7())
        async with session_factory() as session:
            await session.execute(
                text(
                    "INSERT INTO recipient_channels (id, recipient_id, kind, target, enabled,"
                    " include_names, on_local_network, created_at, updated_at)"
                    " VALUES (:cid, :rid, 'email', 'y@example.com', TRUE, FALSE, FALSE,"
                    " timezone('utc', now()), timezone('utc', now()))"
                ),
                {"cid": second["channel_id"], "rid": ids["recipient_id"]},
            )
            await session.commit()
        async with session_factory() as session:
            written = await write_delivery_rows(session, [_planned(ids), _planned(second)])
            await session.commit()
        assert written == 2
        async with session_factory() as session:
            keys = (
                (
                    await session.execute(
                        select(NotificationDelivery.idempotency_key).where(
                            NotificationDelivery.alert_id == ids["alert_id"]
                        )
                    )
                )
                .scalars()
                .all()
            )
            # The uq_notification_deliveries_idem constraint holds and the two
            # rows differ (distinct channels -> distinct keys).
            assert len(set(keys)) == len(keys) == 2

    async def test_records_without_alert_ids_are_skipped(
        self, session_factory, clean_tables
    ) -> None:
        ids = await _seed_parents(session_factory)
        # A dict record without alert_id cannot become a row (the FK would be
        # violated); the writer skips it and counts only the PlannedDelivery.
        orphan = {"recipient_id": ids["recipient_id"], "channel_id": ids["channel_id"]}
        async with session_factory() as session:
            written = await write_delivery_rows(session, [_planned(ids), orphan])
            await session.commit()
        assert written == 1
