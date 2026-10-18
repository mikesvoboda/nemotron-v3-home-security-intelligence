"""B3.3: the checked, ordered schema-upgrade runner.

`backend/migrations/AGENTS.md` first. In one paragraph:

``schema_migrations`` records which upgrades a database has had. For each registered upgrade in
order: already recorded -> nothing happens; else the upgrade's live-catalog CHECK (`checks.py`)
asks whether the effect is already in place and, if so, the upgrade is recorded WITHOUT running
its SQL (`executed = false`); else the SQL runs and is recorded. The CHECK, the SQL and the
record for one upgrade share ONE transaction, so an upgrade and its record land together or not
at all, and a concurrent worker cannot slip between the check and the record.

Why not "just run the files": three of the four are ``IF NOT EXISTS``-idempotent, but NEM-5051 is
``ALTER TABLE ... ALTER COLUMN ... TYPE jsonb``, which rewrites the column and takes
``ACCESS EXCLUSIVE`` on ``alerts`` and ``alert_rules``. A database that `create_all` built
already has those columns as ``jsonb``, so blind re-apply would take that lock on every boot and
would fail outright the day a view depends on one of the columns. "Idempotent" is a property of
the file; "already in place" is a property of the database. The runner asks the second question.

Transaction discipline is the one part that cannot be got wrong quietly, so it is stated:
SQLAlchemy AUTOBEGINS a transaction on the first statement on a connection, and a later
`conn.begin()` then raises "This connection has already initialized a SQLAlchemy
Transaction() object". Every function here therefore either opens its own `conn.begin()` or
documents that the caller's transaction is already open (the `_tx` suffix). The first version of
this module read the records on the bare connection and `--apply` failed on the first upgrade.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from backend.migrations import registry
from backend.migrations.checks import CHECKS
from backend.migrations.errors import UpgradeDriftError, UpgradeError

logger = logging.getLogger(__name__)

#: Written once per database; the name is the contract (`00 §7` names the missing half: nothing
#: in-repo ever recorded which upgrades a database had).
SCHEMA_TABLE = "schema_migrations"

#: One row per applied upgrade. `executed` distinguishes "this database ran the SQL" from "this
#: database already had the effect and we verified it" -- the difference an operator asks about
#: when a change they expected in the startup logs is not there.
# The statements spell the table name as a LITERAL instead of f-stringing SCHEMA_TABLE into
# text(). Deliberate: this repo's `sqlalchemy-raw-text-injection` rule and semgrep's registry
# `avoid-sqlalchemy-text` rule both key on interpolation inside text(), so every legitimate
# dynamic-table use in the codebase carries a hand-placed `nosemgrep` (31 of them for ruff's S608
# alone). A literal plus the import-time check below gives the same guarantee without a pragma a
# future reader would have to trust. `exec_driver_sql` DDL is untouched by those rules and stays
# interpolated.
_CREATE_RECORD_TABLE = f"""
CREATE TABLE IF NOT EXISTS {SCHEMA_TABLE} (
    id          TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    checksum    TEXT NOT NULL,
    executed    BOOLEAN NOT NULL,
    source      TEXT
)
"""
_READ_RECORDS_SQL = text(
    "SELECT id, applied_at, checksum, executed, source FROM schema_migrations ORDER BY id"
)
_INSERT_RECORD_SQL = text(
    "INSERT INTO schema_migrations (id, checksum, executed, source) "
    "VALUES (:id, :checksum, :executed, :source) "
    "ON CONFLICT (id) DO NOTHING"
)
_EXISTS_RECORD_SQL = text("SELECT 1 FROM schema_migrations WHERE id = :id")


def _assert_record_table_spelled_consistently() -> None:
    """Every statement must name `SCHEMA_TABLE` exactly as the constant spells it.

    Fires at import. This is what makes the literal above safe to leave literal: rename the
    constant and the module refuses to import, instead of quietly reading a table nobody writes.
    """
    for statement in (
        _CREATE_RECORD_TABLE,
        _READ_RECORDS_SQL,
        _INSERT_RECORD_SQL,
        _EXISTS_RECORD_SQL,
    ):
        if SCHEMA_TABLE not in str(statement):
            msg = (
                f"a record-table statement does not name SCHEMA_TABLE={SCHEMA_TABLE!r}: "
                f"{str(statement)[:60]}..."
            )
            raise UpgradeError(msg)


_assert_record_table_spelled_consistently()


@dataclass(frozen=True)
class UpgradeResult:
    """What happened to one upgrade during one run."""

    id: str
    state: str  # applied | verified | already_recorded | would_apply
    executed: bool
    statements: int = 0

    def describe(self) -> str:
        if self.state == "already_recorded":
            return f"{self.id}: recorded, nothing to do"
        if self.state == "verified":
            return f"{self.id}: effect already present, recorded without running"
        if self.state == "would_apply":
            return f"{self.id}: NOT applied (--dry-run); {self.statements} statement(s) would run"
        return f"{self.id}: applied ({self.statements} statement(s))"


@dataclass(frozen=True)
class Record:
    """One row of `schema_migrations`."""

    id: str
    applied_at: datetime
    checksum: str
    executed: bool
    source: str | None


# --------------------------------------------------------------------------------------
# Record-table access. `_tx` functions assume the caller's transaction is open.
# --------------------------------------------------------------------------------------


async def ensure_record_table_tx(conn: AsyncConnection) -> None:
    """Create `schema_migrations` if absent. CALLER'S TRANSACTION MUST BE OPEN.

    It is deliberately NOT in `Base.metadata`. A record table that exists only because a model
    declares it would be created by `create_all` on a fresh database and by nothing else -- and
    the case this runner exists for is a database `create_all` already built. Declared here, it
    is created by the same code path that reads it.
    """
    await conn.exec_driver_sql(_CREATE_RECORD_TABLE)


async def read_records_tx(conn: AsyncConnection) -> dict[str, Record]:
    """Every recorded upgrade, keyed by id. CALLER'S TRANSACTION MUST BE OPEN."""
    await ensure_record_table_tx(conn)
    result = await conn.execute(_READ_RECORDS_SQL)
    return {
        row["id"]: Record(
            id=row["id"],
            applied_at=row["applied_at"],
            checksum=row["checksum"],
            executed=row["executed"],
            source=row["source"],
        )
        for row in result.mappings()
    }


async def read_records(conn: AsyncConnection) -> dict[str, Record]:
    """Every recorded upgrade, in its own committed transaction (public entry point)."""
    async with conn.begin():
        return await read_records_tx(conn)


async def _record_tx(conn: AsyncConnection, upgrade: registry.Upgrade, *, executed: bool) -> None:
    """Insert one record. CALLER'S TRANSACTION MUST BE OPEN.

    `ON CONFLICT DO NOTHING` because a second worker that recorded the same upgrade inside its
    own concurrent transaction is not an error -- the upgrade is idempotent by the CHECK that
    let it through, and the first record is the one that counts.
    """
    await conn.execute(
        _INSERT_RECORD_SQL,
        {
            "id": upgrade.id,
            "checksum": upgrade.checksum(),
            "executed": executed,
            "source": upgrade.source,
        },
    )


def _verify_consistency(records: dict[str, Record], upgrades: Sequence[registry.Upgrade]) -> None:
    """Refuse to proceed when the registry and this database's records disagree (`UpgradeDriftError`)."""
    listed = {upgrade.id for upgrade in upgrades}
    orphans = sorted(set(records) - listed)
    if orphans:
        msg = (
            f"{SCHEMA_TABLE} records upgrades this run's registry does not list: {', '.join(orphans)}. "
            "An applied upgrade was deleted or renamed. Restore it, or name the replacement as a "
            "NEW upgrade id -- do not renumber a recorded upgrade."
        )
        raise UpgradeDriftError(msg)

    by_id = {upgrade.id: upgrade for upgrade in upgrades}
    for record in sorted(records.values(), key=lambda r: r.id):
        upgrade = by_id[record.id]
        current = upgrade.checksum()
        if current != record.checksum:
            msg = (
                f"upgrade {record.id}: recorded checksum {record.checksum} does not match "
                f"{registry.MIGRATION_DIR / upgrade.filename} ({current}). A shipped upgrade was "
                "edited after some database applied it. Ship the correction as a NEW upgrade id."
            )
            raise UpgradeDriftError(msg)


# --------------------------------------------------------------------------------------
# The two commands
# --------------------------------------------------------------------------------------


async def plan(
    conn: AsyncConnection,
    upgrades: Sequence[registry.Upgrade] = registry.UPGRADES,
    *,
    nested: bool = False,
) -> list[UpgradeResult]:
    """What this database still needs, changing nothing but the record table.

    Read this as the operator's question "what would I be doing if I ran the upgrade?". The
    catalog queries run in one transaction that is committed without writing, so a `--status`
    against production takes locks only for the `CREATE TABLE IF NOT EXISTS` of the record
    table (which is what makes the answer about a never-upgraded database meaningful).
    `nested=True` runs the queries inside the caller's already-open transaction instead of
    opening one -- which is what `init_db()` needs.
    """
    if nested:
        return await _plan_body(conn, upgrades)
    async with conn.begin():
        return await _plan_body(conn, upgrades)


async def _plan_body(
    conn: AsyncConnection, upgrades: Sequence[registry.Upgrade]
) -> list[UpgradeResult]:
    records = await read_records_tx(conn)
    _verify_consistency(records, upgrades)
    results: list[UpgradeResult] = []
    for upgrade in upgrades:
        if upgrade.id in records:
            results.append(UpgradeResult(upgrade.id, "already_recorded", executed=False))
            continue
        check = CHECKS.get(upgrade.id)
        if check is not None and await check(conn):
            results.append(UpgradeResult(upgrade.id, "verified", executed=False))
            continue
        results.append(
            UpgradeResult(
                upgrade.id, "would_apply", executed=True, statements=len(upgrade.statements())
            )
        )
    return results


async def apply_all(
    conn: AsyncConnection,
    upgrades: Sequence[registry.Upgrade] = registry.UPGRADES,
    *,
    dry_run: bool = False,
    nested: bool = False,
) -> list[UpgradeResult]:
    """Bring this database up to the registry, in order, recording each upgrade.

    Args:
        conn: An open connection on the database to upgrade.
        upgrades: The registry, so a test can pass a small one. Defaults to the real list.
        dry_run: Report `plan()` and change nothing beyond the record table's existence.
        nested: Run each upgrade in a SAVEPOINT instead of its own transaction, for a caller
            that already holds an open transaction -- which is exactly `init_db()`, whose
            advisory-locked session does `create_all` and the upgrades together. Without this,
            per-upgrade `conn.begin()` would raise on the caller's open transaction; with it, a
            failed upgrade still rolls back to just before that upgrade, and the caller's outer
            transaction still decides whether anything persists.

    Returns:
        One `UpgradeResult` per registered upgrade, in registry order.

    Raises:
        UpgradeDriftError: Registry and records disagree (see `_verify_consistency`).
        UpgradeError: A file is missing, or one of its statements fails -- that upgrade and its
            record are both rolled back, so the database is left exactly as it was and the next
            run retries the same upgrade. Upgrades already applied in this run stay applied.
    """
    if dry_run:
        return await plan(conn, upgrades, nested=nested)

    def begin():
        return conn.begin_nested() if nested else conn.begin()

    if nested:
        records = await read_records_tx(conn)
    else:
        async with begin():
            records = await read_records_tx(conn)
    _verify_consistency(records, upgrades)

    results: list[UpgradeResult] = []
    for upgrade in upgrades:
        if upgrade.id in records:
            results.append(UpgradeResult(upgrade.id, "already_recorded", executed=False))
            continue

        # One transaction (or savepoint) for check + action + record: a second worker cannot
        # apply the same upgrade between our check and our record, and a failure leaves no
        # half-written history.
        try:
            async with begin():
                if await _is_recorded_tx(conn, upgrade.id):
                    outcome = UpgradeResult(upgrade.id, "already_recorded", executed=False)
                elif (check := CHECKS.get(upgrade.id)) is not None and await check(conn):
                    await _record_tx(conn, upgrade, executed=False)
                    outcome = UpgradeResult(upgrade.id, "verified", executed=False)
                else:
                    statements = upgrade.statements()
                    for stmt in statements:
                        # exec_driver_sql, NOT text(): text() parses `:name` as a bind parameter
                        # even inside a string literal, so a file containing the JSON literal
                        # '{"x":1}' fails with "A value is required for bind parameter '1'" --
                        # measured, and NEM-5051 already ships `channels::jsonb` casts on every
                        # line. An upgrade file has no bind parameters by construction (it is a
                        # checked-in file, not a query), so handing it to the driver verbatim is
                        # both the correct semantic and the one that cannot misparse.
                        await conn.exec_driver_sql(stmt)
                    await _record_tx(conn, upgrade, executed=True)
                    outcome = UpgradeResult(
                        upgrade.id, "applied", executed=True, statements=len(statements)
                    )
        except Exception as exc:
            msg = f"upgrade {upgrade.id} failed and was rolled back: {exc}"
            raise UpgradeError(msg) from exc

        if outcome.state == "verified":
            logger.info("Schema upgrade %s already in effect; recorded without running", upgrade.id)
        elif outcome.state == "applied":
            logger.warning(
                "Applied schema upgrade %s (%d statement(s))", upgrade.id, outcome.statements
            )
        results.append(outcome)

    return results


async def _is_recorded_tx(conn: AsyncConnection, upgrade_id: str) -> bool:
    """Is this id recorded? CALLER'S TRANSACTION MUST BE OPEN.

    Re-checked inside each upgrade's own transaction rather than trusted from the snapshot read
    at the top of the run, so a concurrent worker that recorded it meanwhile is seen.
    """
    await ensure_record_table_tx(conn)
    result = await conn.execute(_EXISTS_RECORD_SQL, {"id": upgrade_id})
    return result.scalar() is not None


async def upgrade_database(
    engine: AsyncEngine,
    upgrades: Sequence[registry.Upgrade] = registry.UPGRADES,
    *,
    dry_run: bool = False,
) -> list[UpgradeResult]:
    """Open a connection and run `apply_all` on the database `engine` points at."""
    async with engine.connect() as conn:
        return await apply_all(conn, upgrades, dry_run=dry_run)


__all__ = [
    "SCHEMA_TABLE",
    "Record",
    "UpgradeResult",
    "apply_all",
    "ensure_record_table_tx",
    "plan",
    "read_records",
    "read_records_tx",
    "upgrade_database",
]
