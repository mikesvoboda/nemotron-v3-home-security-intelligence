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
        assert get_test_db_url() == base_url.replace(
            "postgresql://", "postgresql+asyncpg://"
        ).replace("postgresql+asyncpg://", "postgresql+asyncpg://")


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
