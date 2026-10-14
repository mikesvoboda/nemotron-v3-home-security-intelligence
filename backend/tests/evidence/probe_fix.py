"""Measurement for the fix, in two parts.

(1) Does assigning `created_at` in the Summary constructor actually reach the
    column, or does `server_default=func.now()` win? If the server default won,
    a fixture-side fix would be a silent no-op.
(2) The 2x3 control matrix: OLD fixture state vs NEW fixture state, each run
    through the real repository under three planner settings. The fix is only
    real if OLD's winner depends on the plan and NEW's does not.

Own scratch database; drops it at the end.
"""

import asyncio
import os
import sys
from datetime import UTC, datetime, timedelta

sys.path.insert(0, "/agents/agent-uplevel-backend/workspace")

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models.camera import Base
from backend.models.summary import Summary, SummaryType
from backend.repositories.summary_repository import SummaryRepository

BASE_URL = os.environ["TEST_DATABASE_URL"]
SCRATCH = "r157_fix_probe"
URL = f"{BASE_URL.rpartition('/')[0]}/{SCRATCH}"

OFF_INDEX = [
    "SET LOCAL enable_indexscan = off",
    "SET LOCAL enable_indexonlyscan = off",
    "SET LOCAL enable_bitmapscan = off",
]
OFF_SEQ = ["SET LOCAL enable_seqscan = off"]
RESET_ALL = [
    "SET LOCAL enable_seqscan = on",
    "SET LOCAL enable_indexscan = on",
    "SET LOCAL enable_indexonlyscan = on",
    "SET LOCAL enable_bitmapscan = on",
]


def rows(new_shape: bool):
    """The fixture's four rows. OLD = timestamps left to the server default.
    NEW = mirrors the values SHIPPED in the fixture: created_at = generated_at
    for every row (production's relationship, since production inserts each
    summary in its own transaction)."""
    now = datetime.now(UTC)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    spec = [
        # (type, content, event_count, ws, we, generated_at, created_at_for_NEW)
        (
            SummaryType.HOURLY.value,
            "Older hourly summary - two high-priority events detected.",
            2,
            now - timedelta(hours=2),
            now - timedelta(hours=1),
            now - timedelta(hours=1, minutes=5),
            now - timedelta(hours=1, minutes=5),
        ),
        (
            SummaryType.HOURLY.value,
            "Latest hourly summary - all clear with no high-priority events.",
            0,
            now - timedelta(hours=1),
            now,
            now - timedelta(minutes=5),
            now - timedelta(minutes=5),
        ),
        (
            SummaryType.DAILY.value,
            "Older daily summary from yesterday.",
            5,
            midnight - timedelta(days=1),
            midnight,
            midnight - timedelta(minutes=5),
            midnight - timedelta(minutes=5),
        ),
        (
            SummaryType.DAILY.value,
            "Latest daily summary - three notable events today.",
            3,
            midnight,
            now,
            now - timedelta(minutes=5),
            now - timedelta(minutes=5),
        ),
    ]
    out = []
    for typ, content, n, ws, we, gen, cat in spec:
        kw = {} if not new_shape else {"created_at": cat}
        out.append(
            Summary(
                summary_type=typ,
                content=content,
                event_count=n,
                event_ids=[],
                window_start=ws,
                window_end=we,
                generated_at=gen,
                **kw,
            )
        )
    return out


async def setup() -> async_sessionmaker:
    admin = create_async_engine(
        f"{BASE_URL.rpartition('/')[0]}/postgres", isolation_level="AUTOCOMMIT"
    )
    async with admin.connect() as cx:
        await cx.execute(text(f"DROP DATABASE IF EXISTS {SCRATCH}"))  # nosemgrep
        await cx.execute(text(f"CREATE DATABASE {SCRATCH}"))  # nosemgrep
    await admin.dispose()
    engine = create_async_engine(URL)
    async with engine.begin() as cx:
        await cx.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False), engine


async def seed(sf, new_shape: bool) -> None:
    async with sf() as db:  # ONE session, ONE commit: the fixture's shape
        for s in rows(new_shape):
            db.add(s)
        await db.commit()


async def winner(sf, gucs, stype) -> tuple[str, int]:
    async with sf() as db:
        for g in RESET_ALL:
            await db.execute(text(g))  # nosemgrep
        for g in gucs:
            await db.execute(text(g))  # nosemgrep
        got = await SummaryRepository(db).get_latest_by_type(stype)
        return got.content, got.event_count


async def main() -> None:
    print("=== (1) does a constructor-assigned created_at survive the round trip? ===")
    print("    (stored created_at == stored generated_at for every row proves it did;")
    print("     the server default would stamp all four with ONE transaction time)")
    sf, engine = await setup()
    await seed(sf, new_shape=True)
    async with engine.connect() as cx:
        stored = (
            await cx.execute(
                text(
                    "SELECT content, created_at, generated_at FROM summaries ORDER BY id"
                )  # nosemgrep
            )
        ).all()
    reached = all(r[1] == r[2] for r in stored)
    for c, cat, gen in stored:
        print(
            f"   {c[:26]:26s} created_at={cat.isoformat()} "
            f"generated_at={gen.isoformat()} equal={cat == gen}"
        )
    print(
        f"   -> {'CONSTRUCTOR VALUE REACHED THE COLUMN' if reached else 'SERVER DEFAULT WON — fix would be a NO-OP'}"
    )
    await engine.dispose()

    print("\n=== (2) winner under each plan: OLD state vs NEW state ===")
    print("    both flaky rows are checked: hourly expects event_count 0, daily expects 3")
    settings = (("default", []), ("index scans off", OFF_INDEX), ("seqscan off", OFF_SEQ))
    expect = {SummaryType.HOURLY: 0, SummaryType.DAILY: 3}
    results: dict[tuple[str, str, str], int] = {}
    for new_shape, label in ((False, "OLD fixture"), (True, "NEW fixture")):
        sf, engine = await setup()
        await seed(sf, new_shape)
        async with engine.begin() as cx:
            await cx.execute(text("ANALYZE summaries"))  # nosemgrep
        for name, gucs in settings:
            for stype in (SummaryType.HOURLY, SummaryType.DAILY):
                content, n = await winner(sf, gucs, stype)
                ok = n == expect[stype]
                results[(label, stype.value, name)] = n
                print(
                    f"   {label} {stype.value:6s} / {name:16s}: {content[:14]:14s} "
                    f"event_count={n} {'-> green' if ok else f'-> RED ({n} != {expect[stype]})'}"
                )
        await engine.dispose()
    print()
    for label in ("OLD fixture", "NEW fixture"):
        for stype in ("hourly", "daily"):
            vals = {results[(label, stype, n)] for n, _ in settings}
            print(
                f"   {label} {stype}: winners across the three plans = {sorted(vals)} -> "
                f"{'PLAN-DEPENDENT (flake)' if len(vals) > 1 else 'plan-INDEPENDENT'}"
            )
    admin = create_async_engine(
        f"{BASE_URL.rpartition('/')[0]}/postgres", isolation_level="AUTOCOMMIT"
    )
    async with admin.connect() as cx:
        await cx.execute(text(f"DROP DATABASE IF EXISTS {SCRATCH} WITH (FORCE)"))  # nosemgrep
    await admin.dispose()
    print(f"\n{SCRATCH} dropped")


asyncio.run(main())
