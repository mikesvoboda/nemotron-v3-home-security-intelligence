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
    """Arm root logging the way a lifespan-booting test does.

    Asserts that it actually armed something: a pin that cannot arm is a pin
    that proves nothing, so this FAILS rather than skips — a skipped child would
    still print a green parent, which is the vacuous-green class this file
    exists to catch. If this fires, root logging is disabled in this environment
    (`data/logs` not writable, or a logging switch), and the fix is the
    environment, not the assertion.
    """
    root = logging.getLogger()
    before = list(root.handlers)
    setup_logging()
    installed = [h for h in root.handlers if h not in before]
    assert installed, (
        "setup_logging() installed no root handlers, so this pair would be vacuous "
        f"(handlers before: {[type(h).__name__ for h in before]!r})"
    )


def test_2_sees_a_restored_root_logger(caplog: pytest.LogCaptureFixture) -> None:
    """The next test must see root as it found it, and an uncached record.

    Handlers are compared by identity, the way `_root_logging_state()` does it:
    `logging` defines no `__eq__`, so an app-installed look-alike cannot be
    confused with one of pytest's own handlers.
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
