"""Live-wiring probe for the r109 root-logging guard — driven by `TestLiveWiring`.

Deliberately named WITHOUT the `test_` prefix: pytest does not auto-collect this
file, so the unit tier never runs it on its own and `-p randomly` can never
shuffle its two tests out of order. `TestLiveWiring` in
`test_root_logging_isolation.py` passes it as an explicit path to a real
`python -m pytest` subprocess, which is what makes it a wiring test at all: the
child session boots the ROOT conftest (`backend/tests/conftest.py`) for real, so
the `pytest_runtest_protocol` hookwrapper is exercised through pytest's own hook
call instead of being called by hand.

Why this file exists: the helper-level tests import `_restore_root_logging()`
and call it directly, and `TestFixtureWiring` only asserts the hook attribute
exists with `hookwrapper=True`. Neither one notices if the hook stops *calling*
the helper — verified 2026-10-11 by deleting the hook's restore body, which left
all of them green. That is the masked-probe class this package keeps hitting.

Order (kept by the parent's `-p no:randomly`) mirrors the real victim pattern:

* `test_1_arms_root_logging_like_a_lifespan_test` does what the security suite's
  `security_client` fixture does — `setup_logging()` via the lifespan path
  (`backend/main.py:808`);
* `test_2_sees_a_restored_root_logger` then asks what the Nightly Full Gate
  victims ask: is root clean, and does a record emitted here carry the cached
  `asctime` key that `logging.Formatter.formatTime` stamps onto records a
  leaky `TraceContextFormatter` handler formatted? A present `asctime` IS the
  batch28_* ratchet failure signature.

With the hook's restore in place, no asctime-formatting handler is attached when
test 2 runs, so nothing caches the key. Delete the restore and test 2 goes red.
"""

from __future__ import annotations

import logging

import pytest

from backend.core.logging import setup_logging

_PROBE_LOGGER = "probe.r109.boundary"


def test_1_arms_root_logging_like_a_lifespan_test() -> None:
    """Arm root logging the way a lifespan-booting test does — and pin WHAT it armed.

    Asserts that it actually armed something *that stamps `asctime`*: a pin that
    cannot arm is a pin that proves nothing, so this FAILS rather than skips — a
    skipped child would still print a green parent, which is the vacuous-green
    class this file exists to catch. If this fires, root logging is disabled in
    this environment (`data/logs` not writable, or a logging switch), and the fix
    is the environment, not the assertion.

    The second half of the assertion is load-bearing for `test_2`, not decoration.
    test_2's teeth come from a leaked `record.asctime`, and `asctime` is only ever
    stamped when the attached formatter's format uses the record's creation time —
    `logging.Formatter.format` calls `formatTime` only when `usesTime()` is true.
    `CONSOLE_FORMAT` carries `%(asctime)s` today (backend/core/logging.py:416, no
    env switch), but the only test that pins that fact outside this file is
    `backend/tests/evidence/test_r109_nightly_gate_harness.py::test_setup_logging_arms_an_asctime_handler_that_leaks`,
    which SKIPS unless `EVIDENCE_R109=1` and no workflow sets that (verified
    2026-10-11: zero hits for `EVIDENCE_R109` outside that directory). Without the
    assertion below, a future format change would leave this test green and quietly
    disarm test_2 — vacuous green again, which is exactly what this file exists to
    refuse. `usesTime()` is asked rather than pattern-matching the format string,
    because it is the same predicate `Formatter.format` itself consults.
    """
    root = logging.getLogger()
    before = list(root.handlers)
    setup_logging()
    installed = [h for h in root.handlers if h not in before]
    assert installed, (
        "setup_logging() installed no root handlers, so this pair would be vacuous "
        f"(handlers before: {[type(h).__name__ for h in before]!r})"
    )
    leakers = [h for h in installed if getattr(h.formatter, "usesTime", lambda: False)()]
    assert leakers, (
        "none of the handlers setup_logging() just armed formats with the record's "
        f"creation time ({[f'{type(h).__name__}:{type(h.formatter).__name__}' for h in installed]!r}) "
        "— test_2's asctime assertion would pass vacuously, because nothing attached "
        "here could ever stamp a cached `asctime`. Either the shipped format changed "
        "(re-derive the leak mechanism) or setup_logging() stopped arming its console "
        "handler (this child no longer witnesses the real boot)."
    )


def test_2_sees_a_restored_root_logger(caplog: pytest.LogCaptureFixture) -> None:
    """The next test must see root as it found it, and an uncached record.

    This test asserts ONE thing: a record emitted here carries no cached
    `asctime`. It does not compare handler lists itself — the identity comparison
    that protects the boundary lives in the root conftest's
    `_root_logging_state()`/`_restore_root_logging()` pair, which this child
    exercises through pytest's own hook call rather than re-doing here. An earlier
    revision of this docstring said "handlers are compared by identity, the way
    `_root_logging_state()` does it", which read as a description of the code
    below it and described code that is not below it (fresh-context review
    `r109-delta-review`, observation 1). What the identity comparison buys is
    stated where it happens; here the witness is the leaked key.
    """
    with caplog.at_level(logging.WARNING, logger=_PROBE_LOGGER):
        logging.getLogger(_PROBE_LOGGER).warning("emitted across the protocol boundary")

    probe_records = [r for r in caplog.records if r.name == _PROBE_LOGGER]
    assert probe_records, "caplog saw nothing; the probe would pass vacuously"
    leaked = [r for r in probe_records if "asctime" in r.__dict__]
    assert not leaked, (
        f"{len(leaked)} record(s) carry a cached 'asctime' — an asctime-formatting root "
        "handler was still attached when this test ran, so the protocol-boundary "
        "restore did not run (this is the batch28_* ratchet failure signature)"
    )
