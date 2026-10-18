"""B3.3: the live-catalog CHECKS behind "has this database already got this upgrade's effect?".

Each check answers a question about the DATABASE, not about the file:

  * file idempotent          -> a property of the SQL text; it means re-running is harmless.
  * effect already in place  -> a property of this database; it means re-running is UNNECESSARY.

Only the second one is what startup needs to know. `create_all` builds today's shape, so on a
fresh database three of the four historical files are already in effect -- running them anyway
would take `ACCESS EXCLUSIVE` on `alerts`/`alert_rules` (NEM-5051's `ALTER COLUMN ... TYPE jsonb`
rewrites the column) on every single boot, and would fail outright if a view ever depended on
those columns. So the runner records those as verified-without-running (`executed = false`) and
moves on.

A listed upgrade with NO entry in `CHECKS` is assumed not-in-place, so its SQL runs. That
default is chosen for the safer failure: it is correct for an idempotent file and it fails loud
for a non-idempotent one on an unrecorded database, which is the case a human must look at.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from backend.migrations.errors import UpgradeNotRegisteredError
from backend.migrations.registry import ids as registry_ids

#: Predicate: True means "the effect is ALREADY in place, do not run the file".
Check = Callable[[AsyncConnection], Awaitable[bool]]

_JSON_COLUMN_QUERY = """
    SELECT count(*) FROM information_schema.columns
    WHERE table_schema = current_schema()
      AND table_name = :table AND column_name = :column AND data_type = 'json'
"""

_ANY_COLUMN_QUERY = """
    SELECT count(*) FROM information_schema.columns
    WHERE table_schema = current_schema()
      AND table_name = :table AND column_name = :column
"""

_ANY_TABLE_QUERY = """
    SELECT count(*) FROM information_schema.tables
    WHERE table_schema = current_schema() AND table_name = :table
"""


async def _count(conn: AsyncConnection, query: str, **params: str) -> int:
    result = await conn.execute(text(query), params)
    return int(result.scalar() or 0)


def column_is_jsonb(table: str, column: str) -> Check:
    """True when the column is no longer plain ``json``.

    Two ways to satisfy it, and both mean "converted": the type is jsonb, or the column is
    gone (a later upgrade dropped it -- re-running a conversion against a missing column is a
    guaranteed error, so it must never be scheduled).
    """

    async def check(conn: AsyncConnection) -> bool:
        if await _count(conn, _ANY_COLUMN_QUERY, table=table, column=column) == 0:
            return True
        return await _count(conn, _JSON_COLUMN_QUERY, table=table, column=column) == 0

    return check


def column_present(table: str, column: str) -> Check:
    """True when the column exists, whatever its SQL-level default says.

    Narrow on purpose: the files' own claims about the DEFAULT belong to the model and to the
    SQL, and the three-way "schema twins" agreement is pinned by
    ``backend/tests/unit/models/test_face_vector_provenance_ddl.py``-style DDL tests, not by
    this check. A missing column is unambiguous; a divergent default on an existing column is
    a different question and this runner does not answer it.
    """

    async def check(conn: AsyncConnection) -> bool:
        return await _count(conn, _ANY_COLUMN_QUERY, table=table, column=column) > 0

    return check


def table_absent(table: str) -> Check:
    """True when the table is gone (the effect of a DROP)."""

    async def check(conn: AsyncConnection) -> bool:
        return await _count(conn, _ANY_TABLE_QUERY, table=table) == 0

    return check


def all_present(checks: Sequence[Check]) -> Check:
    """True only when EVERY predicate says the effect is already in place.

    A file that changes two columns is "already in place" only if both changed: if one did and
    the other did not, the file was interrupted mid-transaction -- which under this runner's
    one-transaction-per-upgrade rule cannot happen -- or the shape arrived from somewhere else
    (a hand-run of part of the runbook, which is exactly the history this package exists to
    retire). Either way the answer is "run the file", and these files are idempotent.
    """

    async def check(conn: AsyncConnection) -> bool:
        # Explicit loop: `all(await c(conn) for c in checks)` is a syntax-level trap -- the
        # comprehension is an ASYNC generator, so `all()` gets a non-iterator and raises
        # TypeError at the first checked upgrade, not at import.
        for predicate in checks:
            if not await predicate(conn):
                return False
        return True

    return check


#: The alert columns NEM-5051 converts, transcribed from the file. The census is
#: `grep -c 'ALTER COLUMN' docs/api/migrations/NEM-5051-convert-alert-json-to-jsonb.sql` = 8:
#: two on ``alerts``, six on ``alert_rules``. It is a transcription, so it can drift from the
#: file; the drift direction is a column the runner does not check, hence `executed = false`
#: for a column it never looked at. `test_checks_cover_every_alter_column_in_the_file` pins
#: this mapping against the file's own text so the drift reddens instead of rotting.
_NEM_5051_COLUMNS: Mapping[str, Sequence[str]] = {
    "alerts": ("channels", "metadata"),
    "alert_rules": (
        "object_types",
        "camera_ids",
        "zone_ids",
        "schedule",
        "conditions",
        "channels",
    ),
}

#: upgrade id -> its predicate. Keys are checked against the registry at import (see
#: `_assert_keys_are_registered`) so a rename in `sql.py` reddens here rather than silently
#: turning a checked upgrade into an unchecked one.
CHECKS: dict[str, Check] = {
    "0001-nem-5051-alert-json-to-jsonb": all_present(
        [
            column_is_jsonb(table, column)
            for table, columns in _NEM_5051_COLUMNS.items()
            for column in columns
        ]
    ),
    "0002-face-vector-provenance-model-id": all_present(
        [
            column_present("face_embeddings", "model_id"),
            column_present("face_detection_events", "model_id"),
        ]
    ),
    "0003-person-vector-provenance-model-id": column_present("person_embeddings", "model_id"),
    "0004-retire-demographics-reid-tables": all_present(
        [table_absent("reid_embeddings"), table_absent("demographics_results")]
    ),
}


def _assert_keys_are_registered() -> None:
    """Every CHECK key must be a registered upgrade id.

    Fires at import. A rename in the registry that leaves a CHECK behind would otherwise turn a
    *checked* upgrade into an unchecked one -- which for an idempotent file is invisible and for
    NEM-5051's is a lock taken on every boot. Better a red import than a silent downgrade of the
    check that protects the startup path.
    """
    unknown = sorted(set(CHECKS) - set(registry_ids()))
    if unknown:
        msg = f"CHECKS has entries for unregistered upgrade ids: {', '.join(unknown)}"
        raise UpgradeNotRegisteredError(msg)


_assert_keys_are_registered()
