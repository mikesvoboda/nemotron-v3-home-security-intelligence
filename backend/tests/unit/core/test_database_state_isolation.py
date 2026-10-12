"""Pin: ``backend.core.database`` module state cannot leak from one unit test to the next (r109c).

main run 38162912077 (merge a195b0984) went red on the coordinator's urgent path:

    test_database_pool.py::TestGetSessionNestedContexts::test_inner_session_rollback_independent
    TypeError: 'MagicMock' object can't be awaited

The victim never touches ``_engine``. A LEAK/INHERIT probe over the full unit tier
(-n 8 --dist=worksteal, probe committed at backend/tests/evidence/
``r109c_leakprobe.py``; NO seed was recorded for that run, and self-review F2 caught this file
claiming otherwise) attributes the poison:
``TestPgbouncerDatabaseInit`` (backend/tests/unit/core/test_pgbouncer_config.py:128-195)
calls the REAL ``init_db()`` with only ``create_async_engine`` patched to a bare
``MagicMock`` (line 146/181) — init_db writes the module singletons
(``_engine``/``_async_session_factory``/``_bound_loop_id``, database.py:126-137) and
``with patch(...)`` restores the function, never the globals. The probe recorded
that triple surviving into 1,278 of the 1,279 INHERIT lines on one worker (gw7) —
32 % of that worker's ~3,964 tests (31,714 passed / 8 workers), not "most of its tier"
(self-review F4). Only 778 of gw7's 1,278 carried ``_bound_loop_id`` as a real int; the
other 500-odd inherited ``loop=None``, which cannot fire the predicate (``database.py:463``)
— so the firing-capable carry is ~20 %, not 32 %.

Why the victim then dies: ``get_session()`` asks ``_check_loop_mismatch()``
(database.py:457-470), which returns True iff ``_engine`` and ``_bound_loop_id`` are
both non-None and ``id(running_loop) != _bound_loop_id``; the branch awaits
``init_db()``, which awaits ``old_engine.dispose()`` on the leaked mock (database.py:230)
— and ``MagicMock().dispose()`` is not awaitable. pytest-asyncio closes each test's
loop and CPython reuses loop addresses, so a fresh loop often lands at the SAME id as
its predecessor and the predicate lies — that memory-address lottery is why a
deterministic leak ships as a "flake" (0 of 31,714 unit tests red on the probe's
order; main's order lost the draw).

The fix mirrors the shipped precedent two screens away in this tier's conftest:
``isolate_redis_module_global`` (backend/tests/unit/conftest.py:52) sweeps
``backend.core.redis`` globals before and after every unit test for the same
xdist-persistence reason. ``backend.core.database`` had no such sweep. The sweep is
test hygiene, not a product change: ``init_db()`` disposing a stale-loop engine is
correct for the shipped process, and the engine was only a mock because a test
leaked it. Placement in the UNIT conftest is deliberate: no unit-tier file constructs
an engine at all. The re-runnable call-site audit is the evidence: every hit of
``grep -rn "create_async_engine(" backend/tests/unit/`` and of the same for
``AsyncEngine(`` is itself a line containing ``grep -rn`` — a docstring quoting this
command, never a construction (add that ``grep -v grep`` to check it; the hit COUNT
grows as docstrings cite it, so the claim is "all hits are citations", not "N hits").
The real references to ``create_async_engine`` are all ``patch(...)`` targets and
prose. The probe could NOT establish
this on its own, for two separate reasons (self-review F5): the run behind the figures
used the probe's original fixture form, whose INHERIT arm filtered real ``AsyncEngine``
out so an all-MagicMock result was tautological; and its LEAK arm is a before/after
delta, so a test that booted a real engine and restored the old value in its own
``finally`` is invisible to it. See
backend/tests/evidence/r109c_leakprobe.py, which is now a hook wrapper for a third
reason F5's follow-up found — under this very sweep a fixture-form probe reports zero
deltas for every test. backend/tests/conftest.py's ``isolated_db`` is left alone here:
it legitimately holds REAL engines for the contracts/integration tiers the unit
conftest does not govern.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

import backend.tests.unit.conftest as unit_conftest
from backend.core import database as db

# The exact message of the main red — asserted verbatim, not "a TypeError".
MAIN_RED_MESSAGE = "'MagicMock' object can't be awaited"

# A loop id no live object can own: enough to satisfy the predicate's non-None arm
# where the test never evaluates it. Same device test_database.py uses (it assigns
# 99999/12345 to _bound_loop_id); stale_loop_id() is for tests that DO call
# _check_loop_mismatch() and need a genuinely different id.
POISONED_LOOP_ID = 99999

# The keys init_db()/close_db() own (database.py:126-137), same set the probe swept.
DB_SINGLETON_KEYS = (
    "_engine",
    "_async_session_factory",
    "_read_engine",
    "_read_session_factory",
    "_bound_loop_id",
)


def stale_loop_id() -> int:
    """An event-loop id guaranteed != the running loop's, for the rest of this test.

    The predicate compares ``id(running_loop) != _bound_loop_id``. Allocating a second
    loop while the current one is alive forces a different id (two live objects never
    share one); closing it leaves that id stale while the CURRENT loop's id can no
    longer change — it was allocated first and is still live. This turns the address
    lottery that made main's red order-dependent into a deterministic premise.
    """
    other = asyncio.new_event_loop()
    try:
        stale = id(other)
    finally:
        other.close()
    assert stale != id(asyncio.get_running_loop()), (
        "determinism broken: the stale loop id equals the running loop's — the pin's "
        "mismatch premise would be false and every test below vacuous"
    )
    return stale


def poison_database_state(stale: int) -> None:
    """Leave the module the way TestPgbouncerDatabaseInit leaves it (probe-verified shape).

    The probe line for the leaker (tick13, gw5/gw7):
        _engine: None -> MagicMock | _async_session_factory: None -> async_sessionmaker
        | _bound_loop_id: None -> int
    A bare MagicMock engine is the load-bearing detail: an AsyncMock would dispose
    cleanly and never raise — only the bare mock produces main's TypeError.
    """
    db._engine = MagicMock()  # bare, exactly like create_async_engine's mock return
    db._async_session_factory = MagicMock()
    db._read_engine = MagicMock()
    db._read_session_factory = MagicMock()
    db._bound_loop_id = stale


def database_state() -> dict:
    return {k: getattr(db, k, "MISSING") for k in DB_SINGLETON_KEYS}


class TestTheMainRedMechanism:
    """The shipped code's behavior under the leak — true before AND after the fix.

    These pin the MECHANISM the sweep removes (per this repo's negative-control
    convention, cf. ``test_control_the_same_boot_does_stamp_asctime`` in
    test_root_logging_isolation.py): if they ever stop raising, the product
    changed and the sweep's docstring claim goes stale.
    """

    async def test_leaked_bare_mock_engine_reaches_dispose_and_raises_main_red(self) -> None:
        # set_trace: mid-test poison, the same state a LEAKING test leaves at exit.
        poison_database_state(stale_loop_id())
        try:
            with pytest.raises(TypeError) as excinfo:
                async with db.get_session():
                    pass
        finally:
            _clear_and_check()
        assert str(excinfo.value) == MAIN_RED_MESSAGE, (
            f"main red was TypeError({MAIN_RED_MESSAGE!r}); this reconstruction "
            f"raised {str(excinfo.value)!r} — mechanism claim is wrong"
        )

    async def test_the_predicate_is_what_fires(self) -> None:
        # Narrower witness one layer down: the mismatch predicate alone, no session.
        poison_database_state(stale_loop_id())
        try:
            assert db._check_loop_mismatch() is True
        finally:
            _clear_and_check()

    async def test_a_matching_loop_id_would_have_hidden_the_leak(self) -> None:
        # Why main's red is order/lottery-shaped, pinned: same poisoned engine, but
        # bound to the CURRENT loop's id → predicate False → no dispose → no raise.
        # The flake is not the mock; it is the id comparison.
        poison_database_state(id(asyncio.get_running_loop()))
        try:
            assert db._check_loop_mismatch() is False
        finally:
            _clear_and_check()


class TestTheSweep:
    """What the conftest fixture's helper must do, pinned directly."""

    async def test_the_helper_clears_every_poisoned_singleton(self) -> None:
        poison_database_state(stale_loop_id())
        try:
            unit_conftest._clear_database_module_state()
            after = database_state()
            assert all(after[k] is None for k in DB_SINGLETON_KEYS), after
        finally:
            _clear_and_check()

    async def test_after_the_sweep_get_session_fails_honestly_not_with_the_mock_typeerror(
        self,
    ) -> None:
        # The guard's guarantee restated as behavior: a later get_session() on swept
        # state takes the shipped "not initialized" path (get_session_factory,
        # database.py:154-166, raising at :164) instead of
        # awaiting a leaked mock. (This cite read ":666-670", which is get_session's
        # docstring Raises block — wrong range, fixed per self-review F9.)
        poison_database_state(stale_loop_id())
        try:
            unit_conftest._clear_database_module_state()
            with pytest.raises(RuntimeError, match="Database not initialized"):
                async with db.get_session():
                    pass
        finally:
            _clear_and_check()

    async def test_the_sweep_is_idempotent_on_clean_state(self) -> None:
        # The redis precedent clears unconditionally at BOTH ends; the second call
        # must be a no-op, not an error, because the fixture runs entry and exit.
        unit_conftest._clear_database_module_state()
        before = database_state()
        unit_conftest._clear_database_module_state()
        assert database_state() == before


class TestTheFixtureItself:
    """Drive the fixture's own generator, so mutating ITS body goes red.

    The TestSweep tests above call the helper directly, which leaves the fixture's
    two halves (entry sweep / exit sweep) unpinned — a mutation that removed one
    half would keep them green. This class calls what pytest calls.
    """

    @staticmethod
    def _run_fixture_body():
        """The generator fixture as pytest drives it: next() = setup, next() = teardown."""
        body = unit_conftest.isolate_database_module_state._fixture_function
        gen = body()
        next(gen)  # entry sweep + yield
        return gen

    async def test_entry_sweep_clears_state_a_previous_test_left(self) -> None:
        # Simulate the handoff: test A poisons, the fixture's SETUP runs, test B's
        # entry state is clean. POISONED_LOOP_ID (not stale_loop_id) because this
        # test never evaluates the predicate — it pins the sweep, not the mismatch.
        poison_database_state(POISONED_LOOP_ID)
        gen = self._run_fixture_body()
        try:
            assert database_state()["_engine"] is None, "fixture entry sweep did not run"
        finally:
            self._finish(gen)

    async def test_exit_sweep_clears_state_this_test_poisoned(self) -> None:
        # The exit half: a test that poisons (like the pgbouncer one) must not pass
        # the poison on, even if its own teardown forgot to.
        gen = self._run_fixture_body()
        poison_database_state(POISONED_LOOP_ID)
        assert database_state()["_engine"] is not None
        self._finish(gen)
        assert database_state()["_engine"] is None, "fixture exit sweep did not run"

    @staticmethod
    def _finish(gen) -> None:
        # Exhausting the generator is what runs the code after `yield` — the exit sweep.
        try:
            next(gen)
        except StopIteration:
            pass


class TestFixtureWiring:
    def test_autouse_sweep_fixture_is_installed_in_the_unit_conftest(self) -> None:
        # The helper is worthless unless the tier runs it per test. pytest 9 wraps
        # decorated fixtures in FixtureFunctionDefinition; the marker (and its
        # autouse/scope, the load-bearing parts) lives on _fixture_function_marker.
        fixture = getattr(unit_conftest, "isolate_database_module_state", None)
        assert fixture is not None, "unit conftest lost the per-test database sweep"
        marker = getattr(fixture, "_fixture_function_marker", None)
        assert marker is not None, f"{fixture!r} is not a @pytest.fixture"
        assert marker.autouse is True, "the sweep must be autouse or it guards nothing"
        assert marker.scope == "function", "a coarser sweep would clear mid-suite state"

    async def test_the_poisoned_state_the_leaker_produces_is_what_the_fixture_clears(self) -> None:
        # One test's exit state is the next test's entry state UNLESS the fixture
        # ran between them — pin the handoff directly: poison "as test A", run the
        # exact callable the fixture calls at entry, assert the next test's view.
        poison_database_state(stale_loop_id())
        entry_view = database_state()
        assert entry_view["_engine"] is not None, "test A must leave the poison set"
        unit_conftest._clear_database_module_state()  # the fixture's entry sweep
        assert database_state()["_engine"] is None


def _clear_and_check() -> None:
    """Teardown for this file's own poisons — never leave the module dirty ourselves."""
    unit_conftest._clear_database_module_state()
