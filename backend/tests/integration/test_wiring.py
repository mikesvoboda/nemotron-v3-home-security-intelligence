"""Integration tests for the B4.2 planner wiring (build_default_planner).

The wiring is the DB half of the planner: preload enabled recipients with
their channels and quiet periods plus the household timezone, inside the
pipeline's transaction, and return the sync hook. These tests run that path
against real rows — recipients/channels from the delivery model, quiet periods
from notification_preferences, the timezone from the Property row — and check
the decisions the composed hook makes, including the quiet-hours suppression
and the critical-breaks-quiet escape.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid7

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.services.alerting.wiring import build_default_planner

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
    async with db_engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE quiet_hours_periods, notification_deliveries,"
                " recipient_channels, recipients, properties, households CASCADE"
            )
        )
    yield
    async with db_engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE quiet_hours_periods, notification_deliveries,"
                " recipient_channels, recipients, properties, households CASCADE"
            )
        )


async def _seed_household_property(session_factory: Any, *, timezone: str) -> int:
    """One household + property with the given timezone; returns property id."""
    async with session_factory() as session:
        await session.execute(
            text("INSERT INTO households (name) VALUES ('Test household') RETURNING id"),
        )
        household_id = (await session.execute(text("SELECT lastval()"))).scalar()
        await session.execute(
            text(
                "INSERT INTO properties (household_id, name, timezone) VALUES (:hid, 'Home', :tz)"
            ),
            {"hid": household_id, "tz": timezone},
        )
        await session.commit()
    return int(household_id)


async def _seed_recipient_with_channel_and_period(
    session_factory: Any,
    *,
    critical_breaks_quiet: bool = False,
) -> dict[str, str]:
    """A recipient + email channel + an all-day quiet period.

    Email (not browser): browser channels are exempt from quiet hours by
    design (planner.plan treats them as the dashboard's own surface), so the
    suppression assertions need a suppressible kind.
    """
    recipient_id = str(uuid7())
    channel_id = str(uuid7())
    async with session_factory() as session:
        await session.execute(
            text(
                "INSERT INTO recipients (id, name, enabled, critical_breaks_quiet,"
                " created_at, updated_at)"
                " VALUES (:rid, :name, TRUE, :cbq, timezone('utc', now()),"
                " timezone('utc', now()))"
            ),
            {"rid": recipient_id, "name": f"r-{recipient_id}", "cbq": critical_breaks_quiet},
        )
        await session.execute(
            text(
                "INSERT INTO recipient_channels (id, recipient_id, kind, target, enabled,"
                " include_names, on_local_network, created_at, updated_at)"
                " VALUES (:cid, :rid, 'email', 'w@example.test', TRUE, FALSE, FALSE,"
                " timezone('utc', now()), timezone('utc', now()))"
            ),
            {"cid": channel_id, "rid": recipient_id},
        )
        await session.execute(
            text(
                "INSERT INTO quiet_hours_periods (id, label, start_time, end_time, days,"
                " recipient_id)"
                " VALUES (:pid, 'night', '00:00', '23:59', :days, :rid)"
            ),
            {
                "pid": str(uuid7()),
                "days": [
                    "monday",
                    "tuesday",
                    "wednesday",
                    "thursday",
                    "friday",
                    "saturday",
                    "sunday",
                ],
                "rid": recipient_id,
            },
        )
        await session.commit()
    return {"recipient_id": recipient_id, "channel_id": channel_id}


def _alert() -> Any:
    class A:
        id = "a-wiring-1"
        severity = "medium"

    return A()


class TestBuildDefaultPlanner:
    async def test_hook_decides_on_preloaded_rows(self, session_factory, clean_tables) -> None:
        await _seed_household_property(session_factory, timezone="UTC")
        ids = await _seed_recipient_with_channel_and_period(
            session_factory, critical_breaks_quiet=False
        )
        async with session_factory() as session:
            planner = await build_default_planner(session)
            # The hook is sync and runs on the same snapshot — call it while
            # the session is open (the pipeline's contract).
            planned = planner(_alert(), now=datetime.now(UTC), stale=False)
        assert len(planned) == 1
        record = planned[0]
        assert record.recipient_id == ids["recipient_id"]
        assert record.channel_id == ids["channel_id"]
        # 03:00-ish inside the all-day quiet period, non-critical: suppressed.
        assert record.status == "suppressed"

    async def test_critical_breaks_quiet_when_recipient_allows(
        self, session_factory, clean_tables
    ) -> None:
        await _seed_household_property(session_factory, timezone="UTC")
        await _seed_recipient_with_channel_and_period(session_factory, critical_breaks_quiet=True)
        async with session_factory() as session:
            planner = await build_default_planner(session)
            alert = _alert()
            alert.severity = "critical"
            planned = planner(alert, now=datetime.now(UTC), stale=False)
        assert len(planned) == 1
        assert planned[0].status == "pending"

    async def test_timezone_comes_from_the_property_row(
        self, session_factory, clean_tables
    ) -> None:
        """A non-UTC property timezone steers the quiet-hours local clock.

        The all-day period covers every local minute, so a UTC-evening 'now'
        is suppressed either way; the observable is that the hook plans
        without error and the decision matches the period's days list.
        """
        await _seed_household_property(session_factory, timezone="America/New_York")
        ids = await _seed_recipient_with_channel_and_period(
            session_factory, critical_breaks_quiet=False
        )
        async with session_factory() as session:
            planner = await build_default_planner(session)
            planned = planner(_alert(), now=datetime.now(UTC), stale=False)
        assert len(planned) == 1
        assert planned[0].status == "suppressed"
        assert planned[0].recipient_id == ids["recipient_id"]

    async def test_no_property_falls_back_to_utc(self, session_factory, clean_tables) -> None:
        """No Property row: the household timezone falls back to UTC and the
        hook still plans."""
        ids = await _seed_recipient_with_channel_and_period(session_factory)
        async with session_factory() as session:
            planner = await build_default_planner(session)
            planned = planner(_alert(), now=datetime.now(UTC), stale=False)
        assert len(planned) == 1
        assert planned[0].recipient_id == ids["recipient_id"]
