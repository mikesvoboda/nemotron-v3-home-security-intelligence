"""Regression tests for the integration cleanup sweep (PR #6553 perf audit).

The ``test-performance-audit`` gate went red because the per-test TRUNCATE
sweep in ``backend/tests/integration/conftest.py`` issued one
``TRUNCATE TABLE <t> CASCADE`` round-trip per table — 74 statements per
sweep, run twice per test — whose wall time on CI runners pushed several
tests over the 10s integration threshold (WP0.5 gate, ci.yml).

These tests pin the repaired contract: ONE
``TRUNCATE TABLE t1, t2, ... CASCADE`` command per sweep instead of N
round-trips (Postgres accepts a comma-separated table list natively;
measured 0.22s vs 0.63s per sweep locally, ~3x, and the saving scales
with per-round-trip latency, which is exactly what CI amplifies).

Precedent for unit-testing integration conftest helpers:
``test_redis_prefix_isolation.py`` (imports ``PrefixedRedis``).
"""

from __future__ import annotations

import pytest

import backend.tests.integration.conftest as integration_conftest
from backend.tests.integration.conftest import _cleanup_test_data


class _RecordingSession:
    """Captures every SQL statement the sweep executes."""

    def __init__(self) -> None:
        self.statements: list[str] = []

    async def execute(self, clause_element):
        self.statements.append(str(clause_element))

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info) -> bool:
        return False


class _FakeEngine:
    pass


@pytest.fixture
def sweep(monkeypatch: pytest.MonkeyPatch) -> _RecordingSession:
    """Run the real ``_cleanup_test_data`` against a recording session."""
    session = _RecordingSession()
    order = ["events", "cameras", "alerts"]
    # Bypass reflection entirely — the module-level memo models the same
    # schema-immutable-per-worker property the real cache relies on.
    monkeypatch.setattr(integration_conftest, "_TABLE_DELETION_ORDER_CACHE", order)
    # _cleanup_test_data does `from backend.core.database import get_engine,
    # get_session` at call time, so patch the source module.
    monkeypatch.setattr("backend.core.database.get_engine", lambda: _FakeEngine())
    monkeypatch.setattr("backend.core.database.get_session", lambda: session)
    return session


async def test_sweep_issues_a_single_truncate_command(sweep: _RecordingSession) -> None:
    """One TRUNCATE per sweep, not one per table (the #6553 regression)."""
    await _cleanup_test_data()

    truncates = [s for s in sweep.statements if s.strip().upper().startswith("TRUNCATE")]
    assert len(truncates) == 1, (
        f"cleanup sweep issued {len(truncates)} TRUNCATE round-trips; the "
        f"post-#6553 contract is exactly one comma-joined TRUNCATE"
    )


async def test_single_truncate_covers_every_table(sweep: _RecordingSession) -> None:
    """The one TRUNCATE lists all tables (CASCADE retained)."""
    await _cleanup_test_data()

    truncates = [s for s in sweep.statements if s.strip().upper().startswith("TRUNCATE")]
    assert len(truncates) == 1
    sql = truncates[0]
    for table in ("events", "cameras", "alerts"):
        assert table in sql, f"table {table!r} missing from sweep: {sql}"
    assert "CASCADE" in sql.upper()


async def test_sweep_still_toggles_replication_role(sweep: _RecordingSession) -> None:
    """FK suppression is opened before and restored after the TRUNCATE."""
    await _cleanup_test_data()

    role_stmts = [s for s in sweep.statements if "session_replication_role" in s]
    assert len(role_stmts) == 2
    assert "replica" in role_stmts[0]
    assert "DEFAULT" in role_stmts[1].upper()
