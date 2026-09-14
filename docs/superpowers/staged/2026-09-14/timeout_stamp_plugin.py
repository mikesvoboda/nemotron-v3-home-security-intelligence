"""Run-8 protocol plugin: make --timeout=30 actually govern integration tests.

backend/tests/conftest.py:_apply_timeout_marker stamps timeout(5) on every
integration item, and pytest-timeout's per-item markers OVERRIDE the CLI
--timeout — so validate.sh's "--timeout=30" integration stage has been
running at a 5s effective cap. Under -n8 contention legitimate tests exceed
5s and pytest-timeout's thread method os._exit(1)s the whole xdist worker
("node down: Not properly terminated", silent — the stack dump goes to the
dead worker's captured stderr). Same class as R-T7-WORKERDOWN, but file-wide.

This plugin's hook runs before the root conftest's (tryfirst): it stamps
timeout(30) on integration items lacking an explicit marker, which makes the
conftest's get_closest_marker("timeout") check fire and leave them at 30.
Repo change NOT shipped here — marker-overrides-CLI landmine + the 5s
integration default are owner-ruling candidates (ledger).
"""

import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items):
    cap = int(config.getoption("timeout") or 0)
    if cap <= 0:
        return
    for item in items:
        if "/integration/" in str(item.fspath) and not item.get_closest_marker("timeout"):
            item.add_marker(pytest.mark.timeout(cap))
