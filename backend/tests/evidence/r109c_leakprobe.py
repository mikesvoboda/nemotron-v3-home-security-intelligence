"""Probe: who LEAKS backend.core.database globals, who INHERITS a dirty state.

The committed tool behind PR #7010's attribution of main run 38162912077's
``TypeError: 'MagicMock' object can't be awaited`` (contract rule 3: tools live
in the repo). Committed as self-review finding F2's remedy — the whole evidence
chain for "who left the poison" rested on this file while it lived only under
/tmp, which is the same rule-3 violation this lane already conceded once
(`r109_discriminator.sh`, same programme, same finding).

**This is the hook-shaped rewrite, not the file that produced the original
figures.** The original was an autouse plugin fixture, and an autouse fixture
loaded with ``-p`` sits at plugin depth — the outermost fixture, so it sets up
first and tears down LAST, after ``backend/tests/unit/conftest.py``'s
``isolate_database_module_state`` sweep has already nulled the globals. Its
entry and exit snapshots are then both "all None" and the delta is zero by
construction: on a tree WITH the sweep it reports a clean bill of health no
matter what the tests do. Measured at this head on 2026-10-11::

    fixture-form probe, over test_database_pool.py
      at merge-base f680b74a6 (no sweep)  -> 5 LEAK lines
      at head f62a584d7   (sweep active)  -> 0 lines
    test_database_pool.py is byte-identical at both heads (git diff = empty)

    fixture-form probe, over all of backend/tests/unit/core/ (3,847 tests, 1
      skipped, at head)                   -> 0 LEAK, 0 INHERIT
    deliberate leaker (sets db._engine = MagicMock) inside the swept dir,
      at head, -n0                        -> 0 lines  [masked]
      same file outside backend/tests/    -> 1 line   [arm is alive]
    THIS hook form, same deliberate leaker at head -> fires
    THIS hook form, over test_database_pool.py -> non-zero at BOTH heads
      (5 and 6 across two draws at merge-base, 5 at head — the exact count moves
      with the worksteal assignment, because a test's entry state depends on
      which worker ran its predecessors. Quote it as "non-zero at both heads",
      never as a fixed count.)

So the fixture-form counts in ``test_database_state_isolation.py`` (1,279
INHERIT, 29 LEAK, 11 of them from ``test_database_pool.py``) remain valid FOR
THE PRE-SWEEP RUN THAT PRODUCED THEM and cannot be re-measured with the old
file on this branch. ``pytest_runtest_call`` is a wrapper that runs inside every
fixture setup and before any teardown, so the window it measures cannot be
laundered by a fixture that cleans up around it.

Usage — this directory goes on ``PYTHONPATH`` because the file is not a package
module; bare ``-p r109c_leakprobe`` and ``-p backend.tests.evidence.r109c_leakprobe``
both raise ModuleNotFoundError from a clean checkout. ``-n 8 --dist=worksteal``
come from the repo's own addopts (``pyproject.toml:545``)::

    PYTHONPATH=backend/tests/evidence LEAKPROBE_OUT=/tmp/leaks.txt \\
        uv run pytest backend/tests/unit/ -p r109c_leakprobe -q

Load line verified at this head over
``backend/tests/unit/core/test_database_state_isolation.py`` (10 passed, plugin
imported cleanly) and over ``test_database_pool.py`` and a controlled leaker as
tabulated above. The full-tier run that produced the figures quoted in
``test_database_state_isolation.py`` used the /tmp fixture-form copy, not this
file, so those counts still need a re-run on a pre-sweep tree to be reproduced.

File-append (not print) so xdist passing tests still record. One line per event:
``<worker> INHERIT <nodeid> :: ...`` for a test that entered the call phase with
a non-None singleton, ``<worker> LEAK <nodeid> :: key: Before -> After`` for a
test whose call phase changed a singleton without restoring it.

Read the arms' limits before quoting them (self-review F5, and the fix to F5's
first half):

* The INHERIT arm no longer filters ``AsyncEngine`` — the old fixture-form probe
  skipped a real engine, so it could never print "inherited a real engine" and
  the all-MagicMock result was tautological. This arm prints the type it finds,
  whatever it is, so an absence of ``engine=AsyncEngine`` is now actual evidence.
* The LEAK arm compares just BEFORE and AFTER the call phase, so a test that
  boots a real engine and restores it in its own ``finally`` leaves zero delta.
  It shows *left-behind* state, not *booted* state.
* INHERIT is measured after the conftest entry sweep runs, so on a tree with the
  sweep it is expected to be ~zero — that is the sweep working, not a dead arm.
  Confirm with the LEAK arm, which stays non-zero under the sweep.

No seed was recorded for the original run, which is the second half of F2 — the
shipped docstring used to say "seed recorded in the PR" when it was not. Re-run
with a seed and add it to the PR rather than quoting the original counts as
reproducible.
"""

import os

import pytest

SNAP_KEYS = (
    "_engine",
    "_read_engine",
    "_async_session_factory",
    "_read_session_factory",
    "_bound_loop_id",
)

OUT = os.environ.get("LEAKPROBE_OUT", "leakprobe.log")


def _t(v):
    return f"{type(v).__name__}" if v is not None else "None"


_LOG_BROKEN = [False]


def _log(line):
    """Append one line; never let the observer break the observed run.

    A missing LEAKPROBE_OUT directory must not turn 5 green tests red — an
    instrument that can do that gets its own I/O errors mistaken for test
    failures (measured: 5 reds, exactly the 5 tests this probe exists to
    report on). An unwritable path degrades to one stderr warning per process
    (measured: 3 lines across 3 xdist workers). The path is deliberately NOT
    created: this tool must not mkdir from an env var.
    """
    try:
        with open(OUT, "a") as f:  # nosemgrep: path-traversal-open
            f.write(line + "\n")
    except OSError as exc:  # pragma: no cover - dev-tool degraded path
        if not _LOG_BROKEN[0]:
            _LOG_BROKEN[0] = True
            import sys

            print(f"r109c_leakprobe: cannot write {OUT}: {exc} — probing disabled", file=sys.stderr)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    """Snapshot the five globals around the call phase only.

    Deliberately NOT an autouse fixture: see the module docstring — a fixture at
    plugin depth tears down after the conftest sweep and reports zero deltas.
    """
    import backend.core.database as db

    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    before = {k: getattr(db, k, None) for k in SNAP_KEYS}
    if before["_engine"] is not None:
        _log(
            f"{worker} INHERIT {item.nodeid} :: engine={_t(before['_engine'])} "
            f"loop={_t(before['_bound_loop_id'])}"
        )
    try:
        outcome = yield
    finally:
        leaks = []
        for k in SNAP_KEYS:
            now = getattr(db, k, None)
            if now is not before[k]:
                leaks.append(f"{k}: {_t(before[k])} -> {_t(now)}")
        if leaks:
            _log(f"{worker} LEAK {item.nodeid} :: " + " | ".join(leaks))
    return outcome
