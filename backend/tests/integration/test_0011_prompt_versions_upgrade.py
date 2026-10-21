"""B3.3 box 4 (R2a row 27): upgrade 0011 on a SAVED pre-upgrade database, with rows.

The box's Done-when reads: "its test checks that every other row survives and that the
changed rows are exactly those four models' rows". That is a claim about ROWS, so like the
sibling `test_schema_upgrade_path.py` it needs a saved database, loaded from a fixture, in
the shape the upgrade expects -- here, `prompt_versions` with the native `aimodel` enum
column and rows for ALL FIVE models.

Two tests:

  1. `test_0011_deletes_exactly_the_four_models_rows` -- a database in the pre-upgrade
     shape runs the whole registry; afterwards the four retired models' rows are gone,
     every nemotron row survives BYTE-IDENTICAL (config_json included), and the column is
     a varchar, not the enum. The "exactly" is measured as a diff: the set of (model,
     version) pairs before minus after is the four models', and the surviving nemotron
     rows compare field-by-field.
  2. `test_0011_is_verified_on_a_create_all_database` -- a fresh `create_all` database
     already has the new shape (varchar column, no retired rows), so 0011 must record
     WITHOUT running: the `verified` branch, which is what a new installation takes.

Why not in test_schema_upgrade_path.py: that file pins the B3.3 box 6 runner story (a
saved schema with its OWN fixture and three theses); this file is box 4's, with its own
fixture table and its own census. Sharing a fixture file would couple two packages'
Done-whens to one diff.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from backend.migrations import registry
from backend.migrations.runner import read_records_tx, upgrade_database
from backend.tests.integration.conftest import (
    _create_worker_database,
    _drop_worker_database,
    _get_postgres_url,
)

pytestmark = pytest.mark.integration

#: The five models a pre-upgrade `prompt_versions` table can hold; the first four retire.
RETIRED_MODELS = ("florence2", "yolo_world", "xclip", "fashion_clip")
UPGRADE_ID = "0011-retire-vision-model-prompts"


#: The saved pre-0011 `prompt_versions` shape: the native enum column and rows for all
#: five models. A file, not inline DDL, for the same reasons the sibling
#: `schema_pre_upgrade.sql` names -- diffable, loadable by hand with psql.
PRE_0011_SQL = Path(__file__).parent / "fixtures" / "prompt_versions_pre_0011.sql"


def _fixture_rows() -> list[tuple[str, int, str]]:
    """The (model, version, config_json) rows the fixture plants.

    Parsed from the fixture's own INSERT text rather than re-typed, so the test's census
    input is what the fixture actually loads (fixture drift reddens in the first assert,
    not silently shrinks the census).
    """
    import re

    text = PRE_0011_SQL.read_text(encoding="utf-8")
    rows: list[tuple[str, int, str]] = []
    for match in re.finditer(r"\('(\w+)',\s*(\d+),\s*'((?:[^']|'')*)'", text):
        model, version, config = (
            match.group(1),
            int(match.group(2)),
            match.group(3).replace("''", "'"),
        )
        rows.append((model, version, config))
    return rows


@pytest.fixture
def pre_0011_url(postgres_container) -> Iterator[str]:
    """A fresh database holding the saved pre-0011 prompt_versions shape, dropped after."""
    base_url = _get_postgres_url(postgres_container)
    db_name = f"b33_0011_{uuid.uuid4().hex[:8]}"
    url = _create_worker_database(base_url, db_name)
    try:
        import psycopg2

        with psycopg2.connect(url.replace("+asyncpg", "")) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(PRE_0011_SQL.read_text(encoding="utf-8"))
        yield url
    finally:
        _drop_worker_database(base_url, db_name)


async def _row_census(conn: AsyncConnection) -> dict[tuple[str, int], str]:
    """Every row as (model, version) -> config_json, the census the Done-when is about."""
    result = await conn.exec_driver_sql(
        "SELECT model, version, config_json FROM prompt_versions ORDER BY id"
    )
    return {(row[0], row[1]): row[2] for row in result.all()}


async def _model_column_type(conn: AsyncConnection) -> str | None:
    result = await conn.exec_driver_sql(
        "SELECT data_type FROM information_schema.columns "
        "WHERE table_name = 'prompt_versions' AND column_name = 'model'"
    )
    return result.scalar()


async def _model_column_length(conn: AsyncConnection) -> int | None:
    """`character_maximum_length` -- the upgrade converts to varchar(32), the length the
    model's `String(32)` declares, so the schema-twins claim is pinned on the column's full
    shape (both `varchar` and `varchar(32)` read `character varying`)."""
    result = await conn.exec_driver_sql(
        "SELECT character_maximum_length FROM information_schema.columns "
        "WHERE table_name = 'prompt_versions' AND column_name = 'model'"
    )
    return result.scalar()


@pytest.mark.timeout(120)
async def test_0011_deletes_exactly_the_four_models_rows(pre_0011_url):
    """The rows the four retired models own are removed; every nemotron row survives."""
    fixture_rows = _fixture_rows()
    assert {m for m, _, _ in fixture_rows} == {"nemotron", *RETIRED_MODELS}, (
        "the fixture must plant all five models or the census is vacuous"
    )

    # statement_cache_size=0: the before-census prepares `SELECT ... FROM prompt_versions`
    # against the enum-typed column; after 0011's ALTER COLUMN ... TYPE varchar that cached
    # plan is invalid and asyncpg raises InvalidCachedStatementError when the after-census
    # re-runs the same SQL on a pooled connection. The schema change is the test's own
    # subject, so the cache has to be off (SQLAlchemy notices the error but only AFTER
    # failing the statement -- and the after-census must succeed to do the measuring).
    engine = create_async_engine(pre_0011_url, connect_args={"statement_cache_size": 0})
    try:
        async with engine.connect() as conn:
            # ---- the "before" state, measured, so fixture drift cannot pass this test ----
            before = await _row_census(conn)
            assert set(before) == {(m, v) for m, v, _ in fixture_rows}, sorted(before)
            assert await _model_column_type(conn) == "USER-DEFINED", (
                "pre-upgrade, the column is the native aimodel enum"
            )

        results = await upgrade_database(engine)
        assert [r.id for r in results] == list(registry.ids())
        # Measured on this fixture database (probe against the live catalog): 0011 is the
        # only upgrade that RUNS -- its check is the only one that must answer False here.
        # The earlier upgrades' checks all see their effect "already present" on a database
        # whose sole real table is prompt_versions (the checkers are shape-detects, so an
        # absent table means nothing left to do), so they record WITHOUT running -- exactly
        # what a real pre-0011 deployment would experience for upgrades whose tables the
        # fixture does not recreate. Pinning the split keeps a check that starts answering
        # False (and therefore runs against rows it must not touch) visible.
        assert all(
            (r.state == "applied" and r.executed)
            if r.id == UPGRADE_ID
            else (r.state == "verified" and not r.executed)
            for r in results
        ), [r.describe() for r in results]

        async with engine.connect() as conn:
            after = await _row_census(conn)

            # ---- the census: changed rows are EXACTLY the four models' ----
            removed = set(before) - set(after)
            added = set(after) - set(before)
            assert added == set(), f"the upgrade added rows: {sorted(added)}"
            assert {m for m, _ in removed} == set(RETIRED_MODELS), (
                f"rows removed outside the four models: {sorted(removed)}"
            )
            assert removed == {(m, v) for m, v, _ in fixture_rows if m in RETIRED_MODELS}

            # ---- every nemotron row survives with its values ----
            expected_survivors = {(m, v): c for m, v, c in fixture_rows if m == "nemotron"}
            assert after == expected_survivors, (
                f"surviving rows differ from the nemotron fixture rows: "
                f"unexpected={sorted(set(after) - set(expected_survivors))} "
                f"missing={sorted(set(expected_survivors) - set(after))}"
            )

            # ---- the column is a varchar now, not the enum ----
            assert await _model_column_type(conn) == "character varying"
            assert await _model_column_length(conn) == 32, (
                "the upgrade converts to varchar(32) -- the length the model's String(32) "
                "declares -- so create_all and migrated databases agree on the full shape"
            )

            # ---- the record says what happened, with the shipped checksum ----
            records = await read_records_tx(conn)
            assert UPGRADE_ID in records
            by_id = {u.id: u for u in registry.UPGRADES}
            assert records[UPGRADE_ID].checksum == by_id[UPGRADE_ID].checksum()
            assert records[UPGRADE_ID].executed is True
    finally:
        await engine.dispose()


@pytest.mark.timeout(120)
async def test_0011_is_verified_on_a_create_all_database(postgres_container):
    """A fresh `create_all` database already has the new shape: 0011 records without running.

    This pins the model side against the migration side: if the model ever grows the enum
    back (or the column type drifts), create_all builds a database where 0011's check says
    not-in-place, and the file would run a DELETE against fresh rows.
    """
    base_url = _get_postgres_url(postgres_container)
    db_name = f"b33_0011fresh_{uuid.uuid4().hex[:8]}"
    url = _create_worker_database(base_url, db_name)
    engine = create_async_engine(url)
    try:
        from backend.models.camera import Base as ModelsBase

        async with engine.begin() as conn:
            await conn.run_sync(ModelsBase.metadata.create_all)

        results = await upgrade_database(engine)
        states = {r.id: r.state for r in results}
        assert states[UPGRADE_ID] == "verified", [
            r.describe() for r in results if r.id == UPGRADE_ID
        ]
        assert not any(r.id == UPGRADE_ID and r.executed for r in results), (
            "a verified upgrade must run zero statements"
        )
    finally:
        await engine.dispose()
        _drop_worker_database(base_url, db_name)
