"""B3.3 CLI: `python -m backend.migrations` -- the upgrade command ruling 203 asks for.

    uv run python -m backend.migrations            # apply what this database is missing
    uv run python -m backend.migrations --status    # report, change nothing
    uv run python -m backend.migrations --dry-run   # exactly what --apply would do, without doing it

`--status` is the read an operator runs before they touch anything; it also names registry drift
(an upgrade id recorded but not listed, a recorded checksum that no longer matches, a `.sql`
file in the directory no upgrade lists) instead of staying quiet about it.

Exit codes: 0 done, 1 drift or a failing upgrade (the message names the upgrade), 2 the database
is unreachable. 1 rather than 0 on drift is the point -- a startup that ignores drift boots a
database whose history it cannot describe.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

from backend.migrations import registry
from backend.migrations.errors import UpgradeDriftError, UpgradeError
from backend.migrations.runner import SCHEMA_TABLE, apply_all, read_records


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m backend.migrations",
        description="Apply the recorded schema upgrades this database has not had.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--status",
        action="store_true",
        help="report what is recorded and what is owed; change nothing",
    )
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="report what --apply would run; change nothing beyond the record table",
    )
    mode.add_argument("--apply", action="store_true", help="apply what is owed (the default)")
    parser.add_argument(
        "--database-url",
        default=None,
        help="override settings' DATABASE_URL (a postgresql+asyncpg:// URL)",
    )
    return parser.parse_args(argv)


async def _run(args: argparse.Namespace) -> int:
    from backend.core.config import get_settings

    url = args.database_url or get_settings().database_url
    if not url.startswith("postgresql+asyncpg://"):
        print(
            f"error: this command needs an asyncpg URL, got {url.split('://')[0]}://...",
            file=sys.stderr,
        )
        return 2

    engine = create_async_engine(url)
    try:
        if args.status:
            async with engine.connect() as conn:
                records = await read_records(conn)
                results = await apply_all(conn, dry_run=True)
            _print_status(records, results)
            return 0

        async with engine.connect() as conn:
            results = await apply_all(conn, dry_run=args.dry_run)
        for result in results:
            print(result.describe())
        owed = [r for r in results if r.state in {"applied", "would_apply"}]
        if not owed:
            print("nothing owed: every recorded upgrade is in place")
        return 0
    except (UpgradeDriftError, UpgradeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except SQLAlchemyError as exc:
        print(f"error: cannot reach the database: {exc}", file=sys.stderr)
        return 2
    finally:
        await engine.dispose()


def _print_status(records: dict, results: list) -> None:
    if records:
        print(f"recorded in {SCHEMA_TABLE}:")
        for record in sorted(records.values(), key=lambda r: r.id):
            how = "ran the SQL" if record.executed else "verified already in place"
            print(f"  {record.id}  {record.applied_at:%Y-%m-%dT%H:%M:%SZ}  {how}")
    else:
        print(f"nothing recorded in {SCHEMA_TABLE} yet")

    owed = [r for r in results if r.state != "already_recorded"]
    if owed:
        print("owed by this database:")
        for result in owed:
            print(f"  {result.describe()}")
    else:
        print("nothing owed: every listed upgrade is recorded")

    unlisted = registry.unlisted_files()
    if unlisted:
        print(
            "DRIFT: SQL files in the migrations directory that no upgrade lists "
            "(they will never be applied):",
            file=sys.stderr,
        )
        for name in unlisted:
            print(f"  {name}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_run(_parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
