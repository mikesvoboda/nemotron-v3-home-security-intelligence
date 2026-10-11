"""Pin: production logging armed by one test cannot leak into the next (r109).

The Nightly Full Gate unit tier runs unit+contracts+security in one process per
xdist worker with randomized order (repo addopts carry ``-p randomly``), and the
batch28_* logging ratchets assert on ``record.__dict__`` minus a baseline. The
shipped app lifespan calls ``setup_logging()`` (backend/main.py:808), which arms
root handlers whose ``TraceContextFormatter`` stamps ``record.asctime`` onto
EVERY later-propagated record — the same objects caplog holds — so the stamp
reads as "extra payload mutated" / "the shipped WARNING passes no extra=". The
first lifespan-booting test of each worker arms it for every later test of that
worker; which victims go red is order-dependent (measured 2026-10-11, PR #7003:
nightly run 26's red pair vs this sandbox's red set share the 'asctime' key but
not the files). setup_logging() is CORRECT for production — the shipped process
wants its logging — so the fix is test hygiene: the root conftest snapshots root
state before each test and restores it after.

These are contract tests for that restore helper, in the shape of
backend/tests/test_db_isolation.py (helper-level, hermetic, no app boot).
"""

from __future__ import annotations

import logging

import backend.tests.conftest as root_conftest
from backend.tests.conftest import _restore_root_logging, _root_logging_state

# A logger name nothing ships: the pin's records must not be anyone else's.
PIN_LOGGER = "r109.root.logging.isolation.pin"


def boot_fake_production_logging() -> logging.Handler:
    """Install what ``setup_logging()`` installs on root: asctime handlers, a
    root filter, and third-party level drops (backend/core/logging.py:852-916).

    A copy of the SHAPE, not a call into the shipped function: the shipped
    function reads Settings, opens ``data/logs`` and logs two startup records,
    which makes the pin depend on environment. The leak this pins is carried by
    the shape (asctime-bearing root handler), not by the function's identity;
    ``test_autouse_fixture_is_installed`` plus the full-tier repro tie the shape
    back to the shipped call.
    """
    root = logging.getLogger()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    root.addHandler(handler)
    root.addFilter(logging.Filter("r109-pin-filter"))
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    return handler


class TestRestoreRootLogging:
    def test_removes_handlers_installed_during_the_test(self) -> None:
        state = _root_logging_state()
        leaked = boot_fake_production_logging()
        try:
            _restore_root_logging(state)
        finally:
            leaked.close()
        assert leaked not in logging.getLogger().handlers

    def test_keeps_pytest_own_handlers_in_order(self) -> None:
        # pytest arms its live/file handlers at session start (and caplog
        # appends its capture handler per test, removing it in its own
        # teardown, which runs BEFORE this autouse fixture's teardown). The
        # restore must put the snapshot back by identity and order — a
        # re-ordered root breaks pytest's own capture.
        state = _root_logging_state()
        before = list(logging.getLogger().handlers)
        _restore_root_logging(state)
        assert logging.getLogger().handlers == before

    def test_closes_the_installed_handlers(self) -> None:
        # The file handler must be CLOSED, not just detached: it holds a real
        # rotating file open, and 25 leaked instances per worker is a fd leak.
        state = _root_logging_state()
        leaked = boot_fake_production_logging()
        closed = _restore_root_logging(state)
        assert closed >= 1
        assert leaked not in logging.getLogger().handlers

    def test_third_party_levels_are_restored(self) -> None:
        state = _root_logging_state()
        original = logging.getLogger("uvicorn.access").level
        logging.getLogger("uvicorn.access").setLevel(logging.DEBUG)
        _restore_root_logging(state)
        assert logging.getLogger("uvicorn.access").level == original
        # state = (handlers, filters, root level, third-party levels)
        assert logging.getLogger("uvicorn.access").level == state[3]["uvicorn.access"]

    def test_filters_installed_during_the_test_are_dropped(self) -> None:
        state = _root_logging_state()
        boot_fake_production_logging()
        _restore_root_logging(state)
        assert not [
            f for f in logging.getLogger().filters if getattr(f, "name", "") == "r109-pin-filter"
        ]


class TestTheR109FailureMode:
    def test_record_emitted_after_restore_carries_no_asctime(self, caplog) -> None:
        # The exact nightly red, end to end: a later test captures its own
        # record; with the leaked handler restored away, nothing stamps
        # asctime onto it, so an extra= comparison sees only the payload.
        state = _root_logging_state()
        leaked = boot_fake_production_logging()
        _restore_root_logging(state)
        leaked.close()
        with caplog.at_level(logging.WARNING):
            logging.getLogger(PIN_LOGGER).warning(
                "post-restore record", extra={"payload": "only-key"}
            )
        record = caplog.records[-1]
        assert record.msg == "post-restore record"
        # The key the nightly diffs on: an asctime-bearing handler formatted
        # this record during emit, and formatTime caches the stamp on the
        # record object caplog keeps.
        assert not hasattr(record, "asctime")
        assert record.payload == "only-key"

    def test_control_the_same_boot_does_stamp_asctime(self, caplog) -> None:
        # Negative control for the pin above: with the boot NOT restored, the
        # same capture gains asctime — proving the mechanism, not just its
        # absence, and that this pin would go red if the restore broke.
        state = _root_logging_state()
        leaked = boot_fake_production_logging()
        try:
            with caplog.at_level(logging.WARNING):
                logging.getLogger(PIN_LOGGER).warning(
                    "leaked-boot record", extra={"payload": "only-key"}
                )
        finally:
            _restore_root_logging(state)
            leaked.close()
        record = caplog.records[-1]
        assert hasattr(record, "asctime"), (
            "control broken: the asctime-bearing root handler did not stamp a "
            "later record — this file's asctime mechanism claim is false and "
            "the pin above proves nothing"
        )


class TestFixtureWiring:
    def test_hook_is_installed_in_the_root_conftest(self) -> None:
        # The helper is worthless unless something calls it per test. The root
        # conftest (backend/tests/conftest.py) governs every tier below it and
        # installs a pytest_runtest_protocol hookwrapper for that (a protocol
        # boundary sits outside caplog's own handler add/remove, so the restore
        # cannot race it).
        hook = getattr(root_conftest, "pytest_runtest_protocol", None)
        assert callable(hook), "root conftest lost the per-test root-logging restore"
        # hookwrapper=True is load-bearing: a plain impl would REPLACE pytest's
        # own protocol instead of wrapping it, and no test would run at all.
        # pluggy records the opts as a dict on <project>_impl (pluggy
        # HookimplMarker.setattr_hookimpl_opts); "hookwrapper" is the old-style
        # (Result-yielding) wrapper flag this conftest's other hook uses.
        opts = getattr(hook, "pytest_impl", None)
        assert isinstance(opts, dict) and opts.get("hookwrapper"), (
            f"pytest_runtest_protocol must be registered with hookwrapper=True, got {opts!r}"
        )
