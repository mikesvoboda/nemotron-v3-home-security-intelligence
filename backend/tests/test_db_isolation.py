"""Contract tests for per-worker test-database isolation (fast-confidence-loop SS3.1).

These assert the CONTRACT of the helper functions conftest grows, not fixture
behavior: name derivation must be deterministic per worker and collision-free
across workers; helpers must be idempotent and must refuse to drop protected
databases. Run live (helpers act on the real dev Postgres validate.sh exports).
"""

from __future__ import annotations

import os

import pytest

from backend.tests.conftest import (
    _create_worker_database,
    _drop_worker_database,
    worker_db_name,
    worker_id,
)

PROTECTED = ("security", "security_test", "postgres", "template1")


class TestWorkerId:
    def test_defaults_to_master_without_xdist(self, monkeypatch):
        monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
        assert worker_id() == "master"

    def test_reads_env_under_xdist(self, monkeypatch):
        monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw3")
        assert worker_id() == "gw3"


class TestWorkerDbName:
    def test_master_gets_deterministic_name(self, monkeypatch):
        monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
        name = worker_db_name("postgresql+asyncpg://u:p@localhost:5432/base")
        assert name.endswith("_main")
        assert len(name) <= 63  # NAMEDATALEN limit

    def test_gw_suffix_applied(self, monkeypatch):
        monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw7")
        name = worker_db_name("postgresql+asyncpg://u:p@localhost:5432/base")
        assert name.endswith("_gw7")

    def test_distinct_across_workers(self, monkeypatch):
        names = set()
        for wid in ("master", "gw0", "gw1", "gw14", "gw15"):
            monkeypatch.setenv("PYTEST_XDIST_WORKER", wid)
            name = worker_db_name("postgresql+asyncpg://u:p@localhost:5432/base_db")
            assert name not in names, f"collision at {wid}: {name}"
            names.add(name)

    def test_sanitized_prefix_from_base(self, monkeypatch):
        monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw0")
        name = worker_db_name("postgresql+asyncpg://u:p@h:5432/Security_DB-1")
        assert name.startswith("security_db_1_")
        assert all(c.isalnum() or c == "_" for c in name)


@pytest.fixture(scope="session")
def base_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("no TEST_DATABASE_URL/DATABASE_URL exported (run under validate.sh env)")
    return url


class TestCreateDrop:
    def test_create_is_idempotent_and_urls_point_at_worker_db(self, base_url):
        name = "fcl_probe_gw0"
        url1 = _create_worker_database(base_url, name)
        url2 = _create_worker_database(base_url, name)  # second create must not raise
        assert url1 == url2
        assert url1.endswith(f"/{name}")
        assert "+asyncpg" in url1
        _drop_worker_database(base_url, name)

    def test_drop_refuses_protected_names(self, base_url):
        for protected in PROTECTED:
            with pytest.raises(ValueError):
                _drop_worker_database(base_url, protected)

    def test_roundtrip_isolated_from_base(self, base_url):
        from sqlalchemy import create_engine, text

        name = "fcl_probe_gw1"
        url = _create_worker_database(base_url, name)
        try:
            sync_url = url.replace("+asyncpg", "")
            eng = create_engine(sync_url)
            with eng.begin() as conn:
                conn.execute(text("CREATE TABLE fcl_probe (x int)"))
                conn.execute(text("INSERT INTO fcl_probe VALUES (1)"))
            base_eng = create_engine(base_url.replace("+asyncpg", ""))
            with base_eng.begin() as conn:
                exists = conn.execute(
                    text("SELECT 1 FROM information_schema.tables WHERE table_name='fcl_probe'")
                ).fetchone()
            assert exists is None, "worker DB writes leaked into the base database"
        finally:
            _drop_worker_database(base_url, name)


class TestGetTestDbUrlCutover:
    """Re-validation of the cutover that shipped in e8619d80 (M2 Task 6).

    [RECONCILIATION - loud] Plan Task 6 (get_test_db_url -> per-worker URLs,
    TEST_DB_NO_WORKER_SUFFIX opt-out) ALREADY LANDED inside M1 Task 7 as
    e8619d80; its four contract tests shipped with it. This class is
    re-anchoring coverage, not a cutover: the four original tests stay as they
    are, and the two guards the landed tests never pin are added here —
    (a) get_test_db_url must leave TEST_DATABASE_URL/TEST_REDIS_URL in the
    process env untouched (DiskFull lesson: those values come from
    /etc/sandbox-persistent.sh and are load-bearing; nothing may unset or
    default them away), and (b) the URL it hands out must ACTUALLY CONNECT.
    A silently nonexistent database was gate run 9's failure shape (995 x
    InvalidCatalogNameError); no existing contract test would have noticed.
    """

    def test_returns_worker_scoped_url(self, base_url, monkeypatch):
        from backend.tests.conftest import get_test_db_url

        monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw9")
        monkeypatch.setenv("TEST_DATABASE_URL", base_url)
        url = get_test_db_url()
        name = url.rsplit("/", 1)[-1]
        assert name.endswith("_gw9")
        assert name != base_url.rsplit("/", 1)[-1]

    def test_repeat_call_is_stable(self, base_url, monkeypatch):
        from backend.tests.conftest import get_test_db_url

        monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw8")
        monkeypatch.setenv("TEST_DATABASE_URL", base_url)
        assert get_test_db_url() == get_test_db_url()

    def test_master_suffix(self, base_url, monkeypatch):
        from backend.tests.conftest import get_test_db_url

        monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
        monkeypatch.setenv("TEST_DATABASE_URL", base_url)
        url = get_test_db_url()
        assert url.rsplit("/", 1)[-1].endswith("_main")

    def test_opt_out_env_restores_verbatim(self, base_url, monkeypatch):
        from backend.tests.conftest import get_test_db_url

        monkeypatch.setenv("TEST_DATABASE_URL", base_url)
        monkeypatch.setenv("TEST_DB_NO_WORKER_SUFFIX", "1")
        # pre-cutover contract (git show e8619d80^: conftest) — env URL with
        # the asyncpg driver ensured; written as a single normalization so it
        # holds whether base_url already carries "+asyncpg" or not
        assert get_test_db_url() == base_url.replace("postgresql://", "postgresql+asyncpg://")

    def test_opt_out_does_not_disturb_env(self, base_url, monkeypatch):
        # DiskFull lesson: TEST_DATABASE_URL/TEST_REDIS_URL come from
        # /etc/sandbox-persistent.sh and must never be unset or
        # defaulted-away by test code. get_test_db_url reads env, never mutates.
        from backend.tests.conftest import get_test_db_url

        monkeypatch.setenv("TEST_DATABASE_URL", base_url)
        monkeypatch.setenv("TEST_REDIS_URL", "redis://localhost:6379/15")
        monkeypatch.setenv("TEST_DB_NO_WORKER_SUFFIX", "1")
        get_test_db_url()
        assert os.environ["TEST_DATABASE_URL"] == base_url
        assert os.environ["TEST_REDIS_URL"] == "redis://localhost:6379/15"

    def test_returned_url_actually_connects(self, base_url, monkeypatch):
        # Gate run 9's shape: workers pointed at a database that no longer
        # existed (995 InvalidCatalogNameError). Whatever get_test_db_url
        # returns must be live at the moment it is returned. Master-path call
        # ('<base>_main') — a create-if-missing only; this file issues no DROP,
        # so the call is safe next to a live gate.
        from urllib.parse import urlparse

        import psycopg2

        from backend.tests.conftest import get_test_db_url

        monkeypatch.delenv("TEST_DB_NO_WORKER_SUFFIX", raising=False)
        monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
        monkeypatch.setenv("TEST_DATABASE_URL", base_url)
        url = get_test_db_url()
        parsed = urlparse(url.replace("+asyncpg", ""))
        conn = psycopg2.connect(
            host=parsed.hostname or "localhost",
            port=parsed.port or 5432,
            user=parsed.username or "postgres",
            password=parsed.password or "postgres",
            dbname=parsed.path.lstrip("/"),
        )
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                assert cur.fetchone() == (1,)
        finally:
            conn.close()


class TestNameSafetyInvariants:
    """Collision-safety contracts for the naming scheme (spec 3.1, run-9 lesson).

    Gate run 9 died because the integration tier's serial DB is the *bare*
    suffixed-less name ('security_test') while root-tier names are
    '<base>_main'/'<base>_gw<N>' — both tiers keyed their worker names off the
    same server. These tests pin the invariants that keep the two tiers and
    the protected set disjoint; they are pure string logic, no DB needed.
    """

    BASES = (
        "postgresql+asyncpg://u:p@localhost:5432/security",  # box/gate base
        "postgresql+asyncpg://postgres:postgres@localhost:5432/security_test",  # CI base  # pragma: allowlist secret
        "postgresql+asyncpg://u:p@h:5432/postgres",
    )
    WORKERS = ("master", "gw0", "gw7")
    INTEGRATION_NAMES = ("security_test", "security_test_gw0", "security_test_gw7")

    def test_worker_db_name_never_yields_protected_or_base(self, monkeypatch):
        for base in self.BASES:
            base_name = base.rsplit("/", 1)[-1]
            for wid in self.WORKERS:
                monkeypatch.setenv("PYTEST_XDIST_WORKER", wid)
                name = worker_db_name(base)
                assert name not in PROTECTED, f"{base} @ {wid} -> {name}"
                assert name != base_name, f"cutover must never return the base DB: {name}"

    def test_root_names_disjoint_from_integration_tier(self, monkeypatch):
        import re

        for wid in self.WORKERS:
            monkeypatch.setenv("PYTEST_XDIST_WORKER", wid)
            name = worker_db_name(self.BASES[0])  # base = 'security'
            assert name not in self.INTEGRATION_NAMES
            # integration sweep patterns (root cleanup_stale_databases keeps
            # exactly these) must not match root-tier names:
            assert not re.fullmatch(r"test_db_gw[0-9]+", name)
            assert name != "template_test"
            # ...and the root lifecycle sweep pattern (Task 7) must not match
            # integration names or the bare base DB:
            assert not re.fullmatch(r"security_(gw[0-9]+|main)", "security_test")
            assert not re.fullmatch(r"security_(gw[0-9]+|main)", "security")
            assert not re.fullmatch(r"security_(gw[0-9]+|main)", "security_test_gw0")

    def test_serial_names_differ_across_tiers(self, monkeypatch):
        # master (root tier) = 'security_main'; serial integration = 'security_test'
        monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
        assert worker_db_name(self.BASES[0]) == "security_main"
        monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
        assert worker_db_name(self.BASES[1]) == "security_test_main"


class TestSessionLifecycle:
    """Contract tests for the Task 7 lifecycle (memo + sweep + reclaim).

    [RECONCILIATION - loud] Plan Task 7 sketches an autouse session-scoped
    `worker_database` FIXTURE. That name is already taken in root conftest by
    the DEAD template-family fixture the M3-static census maps
    (backend/tests/conftest.py:1210, zero consumers; purge is M3 Task 2's
    pending half) — adding the plan's fixture next to it would shadow it and
    fight the census. Worse, an autouse session fixture fires once per xdist
    WORKER (each worker = its own session), so a sweep written that way runs
    -n times and races itself. The lifecycle therefore ships as
    pytest_sessionstart/pytest_sessionfinish HOOKS (coordination process only)
    + a create-once memo, and these tests pin the collision-safety contracts
    of that shipped shape. Fully offline: DB-touching helpers are monkeypatched
    spies, so this class is safe to run next to a live gate (unlike the
    create/drop classes above, which predate the run-9 lesson).
    """

    BASE = "postgresql+asyncpg://u:p@h:5432/security"

    def test_hooks_are_wired(self):
        import backend.tests.conftest as ct

        for fn in ("pytest_sessionstart", "pytest_sessionfinish"):
            assert callable(getattr(ct, fn)), f"{fn} missing from root conftest"
        for fn in (
            "_memo_worker_database",
            "_sweep_stale_worker_dbs",
            "_reclaim_worker_dbs",
            "_coordination_worker_id",
        ):
            assert callable(getattr(ct, fn)), f"{fn} missing"

    def test_memo_second_call_is_pure_cache_hit(self, monkeypatch):
        import backend.tests.conftest as ct

        monkeypatch.setenv("PYTEST_XDIST_WORKER", "gwt")  # xdist never spawns 'gwt'
        monkeypatch.setattr(ct, "_worker_db_url_cache", {})
        calls: list[str] = []

        def fake_create(base, name):
            calls.append(name)
            return f"postgresql+asyncpg://u:p@h:5432/{name}"

        monkeypatch.setattr(ct, "_create_worker_database", fake_create)
        first = ct._memo_worker_database(self.BASE)
        second = ct._memo_worker_database(self.BASE)
        assert first == second == "postgresql+asyncpg://u:p@h:5432/security_gwt"
        assert calls == ["security_gwt"], "second call must hit the memo, not psycopg2"

    def test_memo_key_covers_worker_and_base_url(self, monkeypatch):
        # A monkeypatched env change must NOT return another worker's URL
        # (stale-URL class: settings cache_clear + wrong DB = contamination).
        import backend.tests.conftest as ct

        monkeypatch.setattr(ct, "_worker_db_url_cache", {})
        seen: set[str] = set()

        def fake_create(base, name):
            seen.add(name)
            return f"postgresql+asyncpg://u:p@h:5432/{name}"

        monkeypatch.setattr(ct, "_create_worker_database", fake_create)
        monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw1")
        u1 = ct._memo_worker_database(self.BASE)
        monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw2")
        u2 = ct._memo_worker_database(self.BASE)
        monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
        u3 = ct._memo_worker_database(self.BASE)
        assert len({u1, u2, u3}) == 3, f"per-worker memo broken: {u1} {u2} {u3}"
        assert seen == {"security_gw1", "security_gw2", "security_main"}

    def test_sweep_membership_and_active_guard(self, monkeypatch):
        # The run-9 invariants as executable code: integration-tier names,
        # the base DB, legacy names and foreign prefixes must never be drop
        # candidates; live names are skipped, not stolen.
        import backend.tests.conftest as ct

        catalog = [
            "security_gw0",  # stale root-tier copy -> drop
            "security_main",  # stale root-tier copy -> drop
            "security_gw3",  # matches, but ACTIVE -> skip
            "security",  # base DB -> never
            "security_test",  # integration serial DB -> never
            "security_test_gw3",  # live gate DB class -> never
            "security_gwX",  # malformed -> never
            "template_test",  # legacy (cleanup_stale_databases' half) -> never
            "test_db_gw2",  # legacy -> never
            "otherprefix_gw1",  # foreign base -> never
        ]
        dropped: list[str] = []
        monkeypatch.setattr(ct, "_list_databases_by_prefix", lambda _base, _prefix: catalog)
        monkeypatch.setattr(
            ct, "_db_has_active_connections", lambda _base, name: name == "security_gw3"
        )
        monkeypatch.setattr(ct, "_drop_worker_database", lambda _base, name: dropped.append(name))
        ct._sweep_stale_worker_dbs(self.BASE)
        assert dropped == ["security_gw0", "security_main"]

    def test_reclaim_is_memo_scoped_and_connection_guarded(self, monkeypatch):
        import backend.tests.conftest as ct

        monkeypatch.setattr(ct, "_worker_dbs_created", {"security_gw5", "security_gw6"})
        live = {"security_gw5"}  # gw5 = a concurrent session still on it
        dropped: list[str] = []
        monkeypatch.setattr(ct, "_db_has_active_connections", lambda _base, name: name in live)
        monkeypatch.setattr(ct, "_drop_worker_database", lambda _base, name: dropped.append(name))
        ct._reclaim_worker_dbs(self.BASE)
        assert dropped == ["security_gw6"]

    def test_reclaim_fail_closed_on_server_loss(self, monkeypatch):
        import psycopg2

        import backend.tests.conftest as ct

        monkeypatch.setattr(ct, "_worker_dbs_created", {"security_gw7"})

        def boom(base, name):
            raise psycopg2.OperationalError("server went away")

        dropped: list[str] = []
        monkeypatch.setattr(ct, "_db_has_active_connections", boom)
        monkeypatch.setattr(ct, "_drop_worker_database", lambda _base, name: dropped.append(name))
        ct._reclaim_worker_dbs(self.BASE)  # must not raise
        assert dropped == []
