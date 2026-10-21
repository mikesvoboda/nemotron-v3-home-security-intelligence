"""B3.3: the live-catalog CHECKS behind "has this database already got this upgrade's effect?".

Each check answers a question about the DATABASE, not about the file:

  * file idempotent          -> a property of the SQL text; it means re-running is harmless.
  * effect already in place  -> a property of this database; it means re-running is UNNECESSARY.

Only the second one is what startup needs to know. `create_all` builds today's shape, so on a
fresh database every registered upgrade is already in effect -- all five, and the census is what
`test_upgrade_command_records_a_create_all_database_without_running_sql` asserts -- so running them anyway
would take `ACCESS EXCLUSIVE` on `alerts`/`alert_rules` (NEM-5051's `ALTER COLUMN ... TYPE jsonb`
rewrites the column) on every single boot, and would fail outright if a view ever depended on
those columns. So the runner records those as verified-without-running (`executed = false`) and
moves on.

A listed upgrade with NO entry in `CHECKS` is assumed not-in-place, so its SQL runs. That
default is chosen for the safer failure: it is correct for an idempotent file and it fails loud
for a non-idempotent one on an unrecorded database, which is the case a human must look at.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Mapping, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from backend.migrations.errors import UpgradeNotRegisteredError
from backend.migrations.registry import UPGRADES
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
        if await _count(conn, _ANY_TABLE_QUERY, table=table) == 0:
            return True
        return await _count(conn, _ANY_COLUMN_QUERY, table=table, column=column) > 0

    return check


def table_absent(table: str) -> Check:
    """True when the table is gone (the effect of a DROP)."""

    async def check(conn: AsyncConnection) -> bool:
        return await _count(conn, _ANY_TABLE_QUERY, table=table) == 0

    return check


def column_absent(table: str, column: str) -> Check:
    """True when the column (or its table) is gone (the effect of a DROP COLUMN)."""

    async def check(conn: AsyncConnection) -> bool:
        if await _count(conn, _ANY_TABLE_QUERY, table=table) == 0:
            return True
        return await _count(conn, _ANY_COLUMN_QUERY, table=table, column=column) == 0

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
#: for a column it never looked at.
#: `test_registry_lexing.py::test_checks_covers_every_alter_column_in_the_nem_5051_file` pins this
#: mapping against the file's own text, so a column dropped from the list reddens instead of rotting.
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


def _add_column_pairs(upgrade_id: str) -> tuple[tuple[str, str], ...]:
    """The `(table, column)` pairs an upgrade's own file adds, read from the shipped text.

    Derived rather than transcribed. `_NEM_5051_COLUMNS` above IS a transcription and says so,
    which means its drift direction is "a column the runner never looked at"; for 0005 the
    column list is 12 long and purely mechanical, so there is no reason to hand-copy it and
    every reason not to. Raises at import if the file adds nothing it can recognise -- a
    reworded file reddens here instead of quietly turning a checked upgrade into an unchecked
    one (`CHECKS` missing a key defaults to "run it", which here would be harmless but silent).
    """
    upgrade = next(u for u in UPGRADES if u.id == upgrade_id)
    pairs = re.findall(
        r"ALTER\s+TABLE\s+(\w+)\s+ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\s+(\w+)",
        " ".join(upgrade.statements()),
        re.IGNORECASE,
    )
    if not pairs:
        raise UpgradeNotRegisteredError(
            f"upgrade {upgrade_id}: no `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` found in "
            f"{upgrade.filename}, so its CHECK cannot be derived. Update the CHECK rather than "
            f"rewording a shipped file (its digest is recorded per database)."
        )
    return tuple(pairs)


#: The 12 columns 0005 adds, derived from its file. Named so the CHECK's shape is inspectable
#: from a shell: `python -c "from backend.migrations.checks import _UNRECORDED_MODEL_COLUMNS"`.
_UNRECORDED_MODEL_COLUMNS: tuple[tuple[str, str], ...] = _add_column_pairs(
    "0005-add-unrecorded-model-columns"
)


def _drop_columns_for_table(upgrade_id: str, table: str) -> tuple[str, ...]:
    """The columns an upgrade's own file drops from `table`, read from the shipped text."""
    upgrade = next(u for u in UPGRADES if u.id == upgrade_id)
    cols = re.findall(
        r"DROP\s+COLUMN\s+IF\s+EXISTS\s+(\w+)",
        " ".join(upgrade.statements()),
        re.IGNORECASE,
    )
    if not cols:
        raise UpgradeNotRegisteredError(
            f"upgrade {upgrade_id}: no `DROP COLUMN IF EXISTS` found in {upgrade.filename} "
            f"for {table}."
        )
    return tuple(cols)


_RETIRED_ALERT_RULE_COLUMNS: tuple[str, ...] = _drop_columns_for_table(
    "0008-retire-alert-rule-pose-action-smoke-columns", "alert_rules"
)


def _prompt_versions_model_migrated() -> Check:
    """True when `prompt_versions.model` is no longer the native `aimodel` enum AND the four
    retired models' rows are gone.

    Both halves matter, and neither alone would record a half-applied upgrade: the column
    conversion without the DELETE would leave rows for models the code no longer knows, and
    the DELETE without the conversion would leave a native enum whose labels still accept
    those models. On a fresh `create_all` database both are true at once (the model side
    ships a plain String column and seeds no retired rows), which is what makes 0011 record
    as ``verified`` on new installs -- the same schema-twins property the upgrade-path test
    pins for the other retirements.
    """

    async def check(conn: AsyncConnection) -> bool:
        type_query = """
            SELECT data_type FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'prompt_versions' AND column_name = 'model'
        """
        result = await conn.execute(text(type_query))
        data_type = result.scalar()
        if data_type is None:
            # No such column/table at all: nothing to migrate, the effect is in place.
            return True
        if data_type != "character varying":
            return False
        rows_query = """
            SELECT count(*) FROM prompt_versions
            WHERE model IN ('florence2', 'yolo_world', 'xclip', 'fashion_clip')
        """
        return await _count(conn, rows_query) == 0

    return check


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
    "0005-add-unrecorded-model-columns": all_present(
        [column_present(table, column) for table, column in _UNRECORDED_MODEL_COLUMNS]
    ),
    "0006-retire-user-calibration-table": table_absent("user_calibration"),
    "0007-retire-action-events-table": table_absent("action_events"),
    "0008-retire-alert-rule-pose-action-smoke-columns": all_present(
        [column_absent("alert_rules", col) for col in _RETIRED_ALERT_RULE_COLUMNS]
    ),
    "0009-retire-gpu-devices-table": table_absent("gpu_devices"),
    "0010-retire-scheduled-reports-table": table_absent("scheduled_reports"),
    "0011-retire-vision-model-prompts": _prompt_versions_model_migrated(),
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
