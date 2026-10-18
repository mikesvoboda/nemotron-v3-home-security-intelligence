"""B3.3 box 6: the upgrade path is checked against a SAVED pre-upgrade database, with rows.

Three theses, one per test:

  1. `test_upgrade_command_brings_a_saved_pre_upgrade_database_up_to_date` -- the command
     (`python -m backend.migrations`, driven here through `upgrade_database`, the call it makes)
     takes a database in the shape `main` leaves behind, ends with today's schema, and keeps every
     pre-existing row. This is the package's Done-when: "a database saved from today's main
     upgrades with its rows intact in CI".
  2. `test_boot_upgrades_a_pre_upgrade_database` -- the same thing happens on startup, because
     `init_db()` runs the upgrades under the same advisory lock as `create_all`. Nothing else in
     the repo can check this: every other test boots a database the fixtures already built.
  3. `test_upgrade_command_records_a_create_all_database_without_running_sql` -- the OTHER half of
     every deployment: a database `create_all` built fresh already has every effect, so the
     command must RECORD all five upgrades and run NO upgrade SQL. This is the branch
     (`state == "verified"`) that a census of the whole suite showed nothing asserted, and it is
     the branch a fresh box takes on every install. Getting it wrong in the pessimistic direction
     means a fresh box runs NEM-5051's `ALTER COLUMN ... TYPE jsonb` at boot; wrong in the
     optimistic direction means the box never records the upgrades and re-runs them forever.

Why a saved .sql fixture and not `drop_all`/`create_all`: `create_all` only ever produces TODAY's
shape, so a test that starts from it cannot express "before". The old shapes live in
`backend/tests/fixtures/schema_pre_upgrade.sql`, and the rows are the point -- an upgrade that
quietly lost data would pass a schema-only check.

The second run is asserted in the SAME database rather than a fresh one, because that is what
every later boot does: it must record nothing and change nothing.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from backend.migrations import registry
from backend.migrations.checks import _UNRECORDED_MODEL_COLUMNS
from backend.migrations.runner import apply_all, read_records_tx, upgrade_database
from backend.tests.integration.conftest import (
    _create_worker_database,
    _drop_worker_database,
    _get_postgres_url,
)

pytestmark = pytest.mark.integration

#: The saved pre-upgrade database. A fixture file, not inline DDL, so it is diffable and loadable
#: by hand (`psql -f`) when someone has to reproduce a failure outside pytest.
PRE_UPGRADE_SQL = Path(__file__).resolve().parents[1] / "fixtures" / "schema_pre_upgrade.sql"

#: The alert columns NEM-5051 converts, spelled as `table.column`. Eight, not seven:
#: `alerts.channels` and `alert_rules.channels` share a column name, and a census keyed on the
#: name alone silently reports 7 where there are 8.
_ALERT_JSON_COLUMNS = (
    "alerts.channels",
    "alerts.metadata",
    "alert_rules.object_types",
    "alert_rules.camera_ids",
    "alert_rules.zone_ids",
    "alert_rules.schedule",
    "alert_rules.conditions",
    "alert_rules.channels",
)


def _load_saved_schema(db_url: str) -> None:
    """Load the saved pre-upgrade schema into an empty database.

    psycopg2, not the runner: this file is the INPUT to the thing under test, so loading it
    through `registry.split_statements` would let the lexer grade its own homework. libpq runs a
    multi-statement script directly, which is also how these files were applied by hand.
    """
    import psycopg2

    with psycopg2.connect(db_url.replace("+asyncpg", "")) as conn:
        # autocommit is an attribute, not a libpq connection parameter: passing it to connect()
        # makes psycopg2 try to parse it as a DSN option and fail with
        # `invalid connection option "autocommit"`. It matters here because CREATE TABLE cannot
        # roll back inside a block that ends in an error, and libpq multi-statement scripts are
        # exactly how these files were applied by hand.
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(PRE_UPGRADE_SQL.read_text(encoding="utf-8"))


@pytest.fixture
def pre_upgrade_url(postgres_container) -> Iterator[str]:
    """A fresh database in the pre-upgrade shape, dropped afterwards.

    One database PER TEST (uuid suffix), not per worker: the retirement upgrade drops two tables,
    so the second test in the same file would otherwise find its "before" state already gone.
    """
    base_url = _get_postgres_url(postgres_container)
    db_name = f"b33_upgrade_{uuid.uuid4().hex[:8]}"
    url = _create_worker_database(base_url, db_name)
    try:
        _load_saved_schema(url)
        yield url
    finally:
        _drop_worker_database(base_url, db_name)


async def _missing_0005_columns(conn: AsyncConnection) -> list[str]:
    """The 0005 columns this database does NOT have yet, as `table.column`.

    A set difference rather than a count, so a failure names which column is missing instead of
    reporting "6 of 12" and leaving someone to find the six.

    The pair list is `checks._UNRECORDED_MODEL_COLUMNS` -- the same derived list the runner's own
    CHECK is built from, which is deliberate: a test that re-typed the 12 names could pass while
    the CHECK it is meant to be checking watched a different list.
    """
    result = await conn.exec_driver_sql(
        "SELECT table_name || '.' || column_name FROM information_schema.columns "
        "WHERE table_schema = current_schema()"
    )
    present = {row[0] for row in result.all()}
    return sorted(
        f"{table}.{column}"
        for table, column in _UNRECORDED_MODEL_COLUMNS
        if f"{table}.{column}" not in present
    )


async def _json_types(conn: AsyncConnection) -> dict[str, str]:
    """`table.column` -> data_type for every json/jsonb column on the alert tables."""
    result = await conn.exec_driver_sql(
        "SELECT table_name || '.' || column_name, data_type FROM information_schema.columns "
        "WHERE table_name IN ('alerts', 'alert_rules') "
        "AND data_type IN ('json', 'jsonb') ORDER BY 1"
    )
    return {row[0]: row[1] for row in result.all()}


# Creating a database, loading a fixture, and running five upgrades is real work; 5s (the
# integration default) cannot fit it. Set from the conftest's own schema-creation ceiling.
@pytest.mark.timeout(120)
async def test_upgrade_command_brings_a_saved_pre_upgrade_database_up_to_date(pre_upgrade_url):
    """Rows in, upgrades run, rows still there -- and a second run is inert."""
    engine = create_async_engine(pre_upgrade_url)
    try:
        async with engine.connect() as conn:
            # ---- the "before" state, measured, so fixture drift cannot pass this test ----
            before = await _json_types(conn)
            assert sorted(before) == sorted(_ALERT_JSON_COLUMNS), before
            assert set(before.values()) == {"json"}, before
            assert (
                await conn.exec_driver_sql(
                    "SELECT count(*) FROM information_schema.tables "
                    "WHERE table_name IN ('reid_embeddings', 'demographics_results')"
                )
            ).scalar() == 2
            assert (
                await conn.exec_driver_sql(
                    "SELECT count(*) FROM information_schema.columns WHERE column_name = 'model_id'"
                )
            ).scalar() == 0
            # 0005's subject matter, measured: a pre-upgrade database has NONE of the twelve
            # January-2026 model columns. If the fixture ever grows one, this fails here rather
            # than letting 0005 report "applied" for a no-op.
            assert await _missing_0005_columns(conn) == sorted(
                f"{table}.{column}" for table, column in _UNRECORDED_MODEL_COLUMNS
            )

        # ---- run the upgrade command ----
        results = await upgrade_database(engine)
        assert [r.id for r in results] == list(registry.ids())
        assert all(r.state == "applied" and r.executed for r in results), [
            r.describe() for r in results
        ]

        async with engine.connect() as conn:
            # ---- the schema moved ----
            after = await _json_types(conn)
            assert sorted(after) == sorted(_ALERT_JSON_COLUMNS), after
            assert set(after.values()) == {"jsonb"}, after

            model_id_tables = {
                row[0]
                for row in (
                    await conn.exec_driver_sql(
                        "SELECT table_name FROM information_schema.columns "
                        "WHERE column_name = 'model_id'"
                    )
                ).all()
            }
            assert {
                "face_embeddings",
                "face_detection_events",
                "person_embeddings",
            } <= model_id_tables

            # ---- the rows survived, with their VALUES ----
            alerts = (
                await conn.exec_driver_sql(
                    "SELECT camera_id, channels::text, metadata::text FROM alerts ORDER BY id"
                )
            ).all()
            assert [a[0] for a in alerts] == ["cam-front", "cam-back", "cam-door"]
            assert '"k": 1' in alerts[0][1] or '"k":1' in alerts[0][1], alerts[0][1]
            assert '"note": "one"' in alerts[0][2] or '"note":"one"' in alerts[0][2], alerts[0][2]
            assert '"deep"' in alerts[2][2], "nested json did not survive the type change"

            provenance = (
                await conn.exec_driver_sql("SELECT model_id FROM face_embeddings ORDER BY id")
            ).all()
            assert len(provenance) == 2, "face_embedding rows were lost"
            assert {p[0] for p in provenance} == {"legacy-unknown-provenance"}
            assert (
                await conn.exec_driver_sql("SELECT count(*) FROM person_embeddings")
            ).scalar() == 3

            # ---- 0005: the twelve unrecorded columns are now present ----
            assert await _missing_0005_columns(conn) == []

            still_present = {
                row[0]
                for row in (
                    await conn.exec_driver_sql(
                        "SELECT tablename FROM pg_tables WHERE schemaname = current_schema()"
                    )
                ).all()
            }
            assert not {"reid_embeddings", "demographics_results"} & still_present

            # ---- and the recorded history says what happened ----
            # The `_tx` variant: this connection's transaction is already open (our own SELECTs
            # autobegan it), and the public read_records() opens a second one, which SQLAlchemy
            # refuses. That is the runner's documented discipline, exercised on the caller side.
            records = await read_records_tx(conn)
            assert set(records) == set(registry.ids())
            assert all(rec.executed for rec in records.values())
            by_id = {u.id: u for u in registry.UPGRADES}
            assert all(records[uid].checksum == by_id[uid].checksum() for uid in records), (
                "recorded checksum does not match the shipped file"
            )

        # ---- every later boot re-runs this; it must record nothing and change nothing ----
        async with engine.connect() as conn:
            second = await apply_all(conn)
            assert [r.state for r in second] == ["already_recorded"] * len(registry.ids())
            assert await _json_types(conn) == after
    finally:
        await engine.dispose()


# Same ceiling: this boots the whole application against the fixture database.
@pytest.mark.timeout(120)
async def test_boot_upgrades_a_pre_upgrade_database(pre_upgrade_url, monkeypatch):
    """`init_db()` runs the upgrades, so a box that merely restarts gets the schema.

    Nothing else in the repo covers this: every other integration test boots a database the
    fixtures already brought to today's shape, so a startup hook that never fired would be
    invisible to all of them.
    """
    from backend.core.config import get_settings
    from backend.core.database import close_db, get_engine, init_db

    original = os.environ.get("DATABASE_URL")
    monkeypatch.setenv("DATABASE_URL", pre_upgrade_url)
    monkeypatch.setenv("ENVIRONMENT", "development")
    get_settings.cache_clear()
    await close_db()
    try:
        await init_db()

        engine = get_engine()
        async with engine.connect() as conn:
            types = await _json_types(conn)
            assert set(types.values()) == {"jsonb"}, types
            records = await read_records_tx(conn)
            assert set(records) == set(registry.ids())
            # create_all holds the same advisory lock and ran first, so the models' tables are
            # present too -- the two halves of startup compose in one transaction.
            assert (
                await conn.exec_driver_sql(
                    "SELECT count(*) FROM information_schema.tables WHERE table_name = 'cameras'"
                )
            ).scalar() == 1
            # And the row the pre-upgrade database carried is still there after a full boot.
            assert (
                await conn.exec_driver_sql("SELECT count(*) FROM person_embeddings")
            ).scalar() == 3
    finally:
        await close_db()
        if original is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original
        get_settings.cache_clear()


# A full create_all over ~90 models plus five CHECK passes over the catalog.
@pytest.mark.timeout(120)
async def test_upgrade_command_records_a_create_all_database_without_running_sql(
    postgres_container,
):
    """A database `create_all` built fresh: record all five upgrades, run NO upgrade SQL.

    This is what a new installation does, and it is the branch nothing else in the repo asserted
    (census: `grep -rn 'state == .verified.' backend/tests/` was empty). The runner answers "is
    this upgrade's effect already in THIS database?" per upgrade, and on a create_all database the
    answer is yes five times: jsonb alert columns (0001), the three provenance columns (0002/0003),
    the two retired tables gone (0004 -- the models no longer define them, so create_all cannot
    bring them back), and the twelve January-2026 columns (0005).

    `executed=False` is asserted twice over -- on the returned results AND on the rows read back
    out of `schema_migrations` -- because the record is the thing later boots trust. A run that
    reported "verified" while writing executed=true would look identical in the log and would
    make the next boot skip an upgrade it never ran.
    """
    base_url = _get_postgres_url(postgres_container)
    db_name = f"b33_fresh_{uuid.uuid4().hex[:8]}"
    url = _create_worker_database(base_url, db_name)
    engine = create_async_engine(url)
    try:
        # TODAY's shape, the way a fresh deployment gets it: create_all and nothing else.
        # Same import the two conftests use for their own create_all (backend.models.camera
        # owns the shared declarative Base), so this test builds what a deploy builds.
        from backend.models.camera import Base as ModelsBase

        async with engine.begin() as conn:
            await conn.run_sync(ModelsBase.metadata.create_all)

        results = await upgrade_database(engine)
        assert [r.id for r in results] == list(registry.ids())
        assert [r.state for r in results] == ["verified"] * len(registry.ids()), [
            r.describe() for r in results
        ]
        assert not any(r.executed for r in results), [r.describe() for r in results]
        assert not any(r.statements for r in results), "a verified upgrade must run zero statements"

        async with engine.connect() as conn:
            records = await read_records_tx(conn)
            assert set(records) == set(registry.ids())
            assert not any(rec.executed for rec in records.values()), {
                uid: rec.executed for uid, rec in records.items()
            }
            by_id = {u.id: u for u in registry.UPGRADES}
            assert all(records[uid].checksum == by_id[uid].checksum() for uid in records)
            # 0005's effect on this database came from create_all, not from the upgrade.
            assert await _missing_0005_columns(conn) == []

        # And the second boot is inert, exactly as test 1's is for an upgraded box.
        async with engine.connect() as conn:
            second = await apply_all(conn)
            assert [r.state for r in second] == ["already_recorded"] * len(registry.ids())
    finally:
        await engine.dispose()
        _drop_worker_database(base_url, db_name)


__all__: list[str] = []  # pytest collects tests; nothing here is importable API
