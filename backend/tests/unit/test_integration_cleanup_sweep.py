"""Regression tests for the integration cleanup sweep.

``_cleanup_test_data`` in ``backend/tests/integration/conftest.py`` runs
before every client-using integration test, so its per-sweep cost is a fixed
tax on the whole tier and its correctness decides whether the tier starts
from a clean database.

These tests pin the contract that landed in #6569 and survived this branch's
merge of main:

1. ONE ``DELETE FROM <table>`` per table, in the reflected FK-safe order.
2. ZERO ``TRUNCATE``. This is the load-bearing one. Remedy ledger
   R-T7-ENOSPC-RECUR bans TRUNCATE here — it allocates a new relfilenode per
   table and defers the unlink to the next checkpoint, which exhausted the
   655K-inode /dev/vdd at ~815 tables x every test x 18 worker DBs. An
   earlier revision of THIS FILE asserted the opposite (exactly one
   comma-joined ``TRUNCATE ... CASCADE``), which is why the guard is now
   stated as a prohibition rather than left implicit.
3. FK suppression opened before the sweep and restored after.

TRUNCATE is also slower on these near-empty tables — measured 2026-09-19 on
postgres:16-alpine, 15 reps: DELETE 0.188 ms/table vs TRUNCATE 1.875
ms/table (10.0x). The batched form is no rescue: one command still churns a
relfilenode per table it names.

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


async def test_sweep_issues_one_delete_per_table(sweep: _RecordingSession) -> None:
    """Exactly one DELETE per table — no redundant round trips."""
    await _cleanup_test_data()

    deletes = [s for s in sweep.statements if s.strip().upper().startswith("DELETE")]
    assert len(deletes) == 3, (
        f"cleanup sweep issued {len(deletes)} DELETE statements for 3 tables; "
        f"the contract is one per table: {deletes}"
    )


async def test_sweep_never_issues_truncate(sweep: _RecordingSession) -> None:
    """TRUNCATE is BANNED on this path (remedy ledger R-T7-ENOSPC-RECUR).

    It allocates a new relfilenode per table and defers the unlink to the next
    checkpoint, which is what exhausted the 655K inodes on /dev/vdd. The
    batched ``TRUNCATE t1, t2, ... CASCADE`` form does not escape this — one
    command still churns a relfilenode per table it names — so the assertion
    is on the STATEMENT being absent entirely, not on how many were issued.
    """
    await _cleanup_test_data()

    truncates = [s for s in sweep.statements if "TRUNCATE" in s.upper()]
    assert truncates == [], (
        "cleanup sweep issued TRUNCATE, which remedy ledger R-T7-ENOSPC-RECUR "
        f"bans on this path (inode exhaustion): {truncates}"
    )


async def test_sweep_covers_every_table(sweep: _RecordingSession) -> None:
    """Every table in the deletion order is actually swept."""
    await _cleanup_test_data()

    swept = " ".join(s for s in sweep.statements if s.strip().upper().startswith("DELETE"))
    for table in ("events", "cameras", "alerts"):
        assert table in swept, f"table {table!r} never swept: {sweep.statements}"


async def test_sweep_still_toggles_replication_role(sweep: _RecordingSession) -> None:
    """FK suppression is opened before and restored after the TRUNCATE."""
    await _cleanup_test_data()

    role_stmts = [s for s in sweep.statements if "session_replication_role" in s]
    assert len(role_stmts) == 2
    assert "replica" in role_stmts[0]
    assert "DEFAULT" in role_stmts[1].upper()
