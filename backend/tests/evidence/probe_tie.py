"""Measurement only — no product file touched.

Question: does `get_latest_by_type`'s `ORDER BY created_at DESC LIMIT 1`
(summary_repository.py:70-74) have a deterministic answer when two rows of the
same type share a created_at, which is what the `multiple_summaries` fixture
creates (one session, one commit, `server_default=func.now()` = Postgres
TRANSACTION timestamp).

Two natural experiments, no invented values:
  A. insertion order — identical values, only the physical order of the two tied
     rows differs. A flip proves the winner comes from scan order, not data.
  B. table size — the fixture's own row count is NOT under its control:
     `clean_summaries` only DELETEs, and xdist workers share this database, so
     other tests' rows may be present. Sweep N and watch the plan and the winner.
Corroboration: the same query under forced planner settings.

Mirror table carries the two indexes the model declares
(backend/models/summary.py:54-55). Drops itself.
"""

import asyncio
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

T = "_r157_tie"
DDL = f"""
CREATE TABLE {T} (
    id SERIAL PRIMARY KEY,
    summary_type VARCHAR(10) NOT NULL,
    content TEXT NOT NULL,
    event_count INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""
IDX = [
    f"CREATE INDEX idx_r157_type_created ON {T} (summary_type, created_at)",
    f"CREATE INDEX idx_r157_created_at ON {T} (created_at)",
]
# the repository's statement, verbatim in shape
Q = (
    f"SELECT id, content, event_count FROM {T} "  # noqa: S608
    "WHERE summary_type = 'hourly' ORDER BY created_at DESC LIMIT 1"
)
# asyncpg refuses multiple commands in one prepared statement, so every GUC
# bundle is a LIST executed one statement at a time.
RESET = [
    "SET LOCAL enable_seqscan = on",
    "SET LOCAL enable_indexscan = on",
    "SET LOCAL enable_indexonlyscan = on",
    "SET LOCAL enable_bitmapscan = on",
]


async def fresh(cx: object) -> None:
    await cx.execute(text(f"DROP TABLE IF EXISTS {T}"))  # type: ignore[union-attr]  # nosemgrep
    await cx.execute(text(DDL))  # type: ignore[union-attr]  # nosemgrep
    for s in IDX:
        await cx.execute(text(s))  # type: ignore[union-attr]  # nosemgrep


def verdict(n: int) -> str:
    return (
        "OLDER row wins -> assert event_count==0 FAILS (2 != 0)"
        if n == 2
        else "LATEST row wins -> test passes"
    )


async def main() -> None:
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])

    # ---------------- Experiment A: insertion order only ----------------
    print("=== A. identical values, different physical insertion order ===")
    for label, seq in (
        ("older row inserted FIRST", [("older", 2), ("latest", 0)]),
        ("latest row inserted FIRST", [("latest", 0), ("older", 2)]),
    ):
        async with engine.begin() as cx:
            await fresh(cx)
            for name, n in seq:  # ONE transaction: this is the fixture's shape
                await cx.execute(
                    text(  # nosemgrep
                        f"INSERT INTO {T} (summary_type, content, event_count) "  # noqa: S608
                        "VALUES ('hourly', :c, :n)"
                    ),
                    {"c": name, "n": n},
                )
            ts = (await cx.execute(text(f"SELECT created_at FROM {T} ORDER BY id"))).scalars().all()  # noqa: S608  # nosemgrep
            got = (await cx.execute(text(Q))).first()  # nosemgrep
            ex = (await cx.execute(text("EXPLAIN " + Q))).scalars().all()  # nosemgrep
            print(
                f"  {label}: created_at equal? {len(set(ts)) == 1}  "
                f"winner={got[1]}(event_count {got[2]}) -> {verdict(got[2])}"
            )
            print("     plan: " + " | ".join(e.strip() for e in ex[:3]))

    # ---------------- Experiment B: how many rows are present ----------------
    print("\n=== B. same tied pair, varying number of other hourly rows ===")
    for count in (0, 5, 100, 5000):
        async with engine.begin() as cx:
            await fresh(cx)
            if count:
                await cx.execute(
                    text(  # nosemgrep
                        f"INSERT INTO {T} (summary_type, content, event_count, created_at) "  # noqa: S608
                        "SELECT 'hourly', 'other ' || g, g % 50, "
                        "       now() - make_interval(mins => 60 + (g % 100000)) "
                        f"FROM generate_series(1, {count}) g"
                    )
                )
            for name, n in (("older", 2), ("latest", 0)):
                await cx.execute(
                    text(  # nosemgrep
                        f"INSERT INTO {T} (summary_type, content, event_count) "  # noqa: S608
                        "VALUES ('hourly', :c, :n)"
                    ),
                    {"c": name, "n": n},
                )
            await cx.execute(text(f"ANALYZE {T}"))  # nosemgrep
            got = (await cx.execute(text(Q))).first()  # nosemgrep
            ex = " | ".join(
                e.strip()
                for e in (await cx.execute(text("EXPLAIN " + Q))).scalars().all()  # nosemgrep
            )
            print(
                f"  N={count:>5}: winner={got[1]}(event_count {got[2]}) -> "
                f"{verdict(got[2])}\n            plan: {ex[:150]}"
            )

    # ---------------- Corroboration: forced planner paths ----------------
    print("\n=== C. same data, forced planner settings ===")
    async with engine.begin() as cx:
        await fresh(cx)
        await cx.execute(
            text(  # nosemgrep
                f"INSERT INTO {T} (summary_type, content, event_count, created_at) "  # noqa: S608
                "SELECT 'hourly', 'other ' || g, g % 50, "
                "       now() - make_interval(mins => 60 + (g % 100000)) "
                "FROM generate_series(1, 5000) g"
            )
        )
        for name, n in (("older", 2), ("latest", 0)):
            await cx.execute(
                text(  # nosemgrep
                    f"INSERT INTO {T} (summary_type, content, event_count) "  # noqa: S608
                    "VALUES ('hourly', :c, :n)"
                ),
                {"c": name, "n": n},
            )
        await cx.execute(text(f"ANALYZE {T}"))  # nosemgrep
        for label, setting in (
            ("default", []),
            (
                "index scans off",
                [
                    "SET LOCAL enable_indexscan = off",
                    "SET LOCAL enable_indexonlyscan = off",
                    "SET LOCAL enable_bitmapscan = off",
                ],
            ),
            ("seqscan off", ["SET LOCAL enable_seqscan = off"]),
        ):
            for s in RESET:
                await cx.execute(text(s))  # nosemgrep
            for s in setting:
                await cx.execute(text(s))  # nosemgrep
            got = (await cx.execute(text(Q))).first()  # nosemgrep
            node = " | ".join(
                e.strip()
                for e in (await cx.execute(text("EXPLAIN " + Q))).scalars().all()  # nosemgrep
            )[:110]
            print(
                f"  {label:>16}: winner={got[1]}(event_count {got[2]}) -> "
                f"{verdict(got[2])}\n          node: {node}"
            )
    async with engine.begin() as cx:
        await cx.execute(text(f"DROP TABLE IF EXISTS {T}"))  # nosemgrep
    await engine.dispose()
    print(f"\ncleaned up: {T} dropped")


asyncio.run(main())
