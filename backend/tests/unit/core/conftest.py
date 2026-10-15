"""Warm the compose CLI once per runner, before any test is timed.

Why this file exists (red `main`, run 38685073281, UR-111/UR-112). The unit tier
here spawns the real compose binary whenever a compose CLI is on PATH
(``test_frontend_expose_lan_bind.py`` and ``test_compose_render_lists_ai_vlm.py``).
The FIRST such spawn on a runner VM pays the docker CLI's compose-plugin cold
start -- the plugin is a ~30 MB binary the CLI must discover and mmap, and the
page cache that holds it is per VM -- and that cost lands inside the spawning
test's own timed window.

Measured in that run's own junit: one slow spawn per shard job, and NOT the same
test each time -- shard 3 ``test_render_unset_binds_loopback`` 5.02 s, shard 4
``test_render_alloy_otlp_binds_loopback`` 2.49 s, shard 1
``test_render_ignores_the_runners_own_bind_address`` 1.92 s, while every later
spawn in the same shard is 0.08-0.10 s. Shard 3's victim crossed the real-sleep
gate's 4.0 s unit budget and reddened ``CI Gate``. The id that pays is chosen by
``--randomly-seed``, so no test here is slow by nature -- the cost belongs to the
runner, and whichever render test the seed orders first just inherits it.

That also explains why the breach *reproduced* under UR-125's re-run: the re-run
is a fresh job on a fresh VM whose page cache is cold again, so the single test
pays the boot again (5.42 s).

Fixing it at the id level would be wrong. ``SLOW_TEST_PATTERNS`` exempts a test
*id*, but the next seed moves the cost to a different id -- a row here would
exempt an innocent test while the red simply migrated. So the cost is paid where
it is actually incurred: once per process, at ``pytest_configure``, which fires
on every xdist worker and on the gate's single-test re-run, BEFORE any test
timer arms. pytest bills a testcase's ``time=`` from setup through teardown only;
hook and import time is not inside any testcase's window. Warming here removes
the breach at its source instead of moving it onto whichever fixture hosted it.

Best-effort by design: if the warm spawn fails for any reason the suite runs on,
unchanged -- only slow again. A harness warm-up must never break or skip the
tests it warms for.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

# What ``pytest_configure`` actually warmed: the argv it ran, or None when no
# compose CLI is on PATH (the pure-Python emulator path, nothing to warm) or the
# warm spawn failed. A holder dict, not a bare global, to stay lint-clean.
_WARMED: dict[str, list[str] | None] = {"argv": None}


def _compose_argv_probe() -> list[str] | None:
    """The compose invocation this machine can run, mirroring the tests' probe.

    A conftest runs before collection, so the test module is not reliably
    importable yet (pytest inserts a test file's directory into ``sys.path``
    during collection, not before). The three modules here that spawn compose
    -- ``test_frontend_expose_lan_bind``, ``test_compose_render_lists_ai_vlm``
    and ``test_monitoring_expose_lan_credentials`` -- each already carry their
    own copy of this probe; this is the fourth.
    ``test_the_compose_probes_have_not_drifted_apart`` pins all four equal and
    ``test_the_warmup_probe_picks_the_tests_binary`` pins that what this hook
    warmed is what the tests spawn, so neither a copy nor the warm-up can drift
    in silence.
    """
    if shutil.which("podman"):
        return ["podman", "compose"]
    if shutil.which("docker"):
        return ["docker", "compose"]
    for binary in ("podman-compose", "docker-compose"):
        if shutil.which(binary):
            return [binary]
    return None


def _warm(argv: list[str]) -> None:
    """Run the cheapest invocation that forces the plugin's cold path.

    ``--version`` resolves the compose subcommand and execs the same plugin
    binary the render tests exec, without needing a project file, an env file or
    a live daemon -- so it cannot fail the way a full ``config`` could, yet it
    still pays the plugin discovery and first exec the render tests would
    otherwise pay inside their own timed window.
    """
    subprocess.run(  # noqa: S603 - argv is a literal list, never a shell string  # real
        [*argv, "--version"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def pytest_configure(config: pytest.Config) -> None:  # pytest hook signature
    """Pay the compose CLI's one-time boot outside every testcase's timed window."""
    argv = _compose_argv_probe()
    if argv is None:
        _WARMED["argv"] = None
        return
    try:
        _warm(argv)
    except Exception:
        # Best-effort on purpose: a warm-up that cannot run must not break or
        # skip the suite it was added to help. The tests stay skip-free and
        # simply run as slow as they did before the warm-up existed.
        _WARMED["argv"] = None
        return
    _WARMED["argv"] = argv


@pytest.fixture(scope="session")
def compose_warmup() -> list[str] | None:
    """Expose what the hook warmed, so a test can pin that it actually ran.

    Reading a recorded value, not doing work: the fixture's setup runs inside a
    testcase's billed window, so warming here would just move the breach onto
    whichever test requested it first. The hook did the warming; this only
    reports it.
    """
    return _WARMED["argv"]
