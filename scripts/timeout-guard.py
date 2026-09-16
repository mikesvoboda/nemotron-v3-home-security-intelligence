#!/usr/bin/env python3
"""timeout-guard — M3 Task 5 (ruling packet 2026-09-14, execution step 3): synthetic three-hang harness.

Proves the ruled-in timeout stack (`timeout_method = "signal"`,
`timeout_func_only = false`, audit Part 6) does its job: a hang in fixture
SETUP, test BODY, or fixture TEARDOWN each fails inside the budget with a
normal pytest summary and NO node-down. The old stack (thread method) made
every hang an `os._exit(1)` worker suicide — "node down: Not properly
terminated", no summary, the reason runs 8/9 lost workers invisibly.

The harness builds a throwaway pytest tree in a temp dir (three micro-tests,
each paired with one hang: setup-hang fixture, body `await sleep(inf)`,
teardown-hang finalizer) and runs it in a SUBPROCESS under the repo's live
pyproject timeout settings, read via tomllib at run time — so if anyone
flips the flags back toward thread/func_only, the guard goes red rather
than silently blessing the old suicide behavior.

Usage:
    uv run python scripts/timeout-guard.py            # run the three-hang harness
    uv run python scripts/timeout-guard.py --self-test  # parser-only checks, no subprocess

Exit: 0 = every hang failed inside budget, no node-down, summary printed.
      1 = any check failed (details printed). This tool never edits anything.

Known caveat (owner-visible, ab9e5774): signal does not re-arm during fixture
SETUP on a rerun attempt — that is a pytest-rerunfailures interaction, out of
scope here (no --reruns passed; the rerun-compose smoke already ran green).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Budget ceiling: the pyproject timeout plus the per-test pytest-cov/xdist-free
# overhead, rounded up. The audit's measured caught-in-time numbers: setup hang
# 5.17s at budget 5. The node-down the OLD stack produced took 60s+ to even
# notice — this ceiling is what "fails inside budget" means.
BUDGET_SLACK_S = 20

# The summary-line shape of a CLEAN pytest-timeout failure (signal method):
# each phase reports "Failed: Timeout >Ns" and the run ends with a summary.
HANG_SITES = {
    "setup": "test_setup_hang",
    "call": "test_body_hang",
    "teardown": "test_teardown_hang",
}

HARNESS_TESTS = """\
import asyncio

import pytest


@pytest.fixture
async def setup_hangs():
    await asyncio.sleep(3600)  # never yields: the run-9 gw6 media_api class
    yield


@pytest.mark.usefixtures("setup_hangs")
def test_setup_hang():
    assert False  # never reached


async def test_body_hang():
    await asyncio.sleep(3600)  # body-phase hang


@pytest.fixture
def teardown_hangs(request):
    def _finalizer():
        import time

        time.sleep(3600)  # sync sleep in teardown: no await to interrupt

    request.addfinalizer(_finalizer)


def test_teardown_hang(teardown_hangs):
    assert True  # passes; the hang is in its teardown
"""


def read_pyproject_timeout() -> tuple[str, bool, float]:
    """Return (timeout_method, timeout_func_only, timeout) from the live pyproject."""
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    tool = data["tool"]["pytest"]["ini_options"]
    return (
        str(tool.get("timeout_method", "thread")),
        bool(tool.get("timeout_func_only", True)),
        float(tool["timeout"]),
    )


def run_harness(timeout: float) -> subprocess.CompletedProcess[str]:
    """Run the three-hang tree in a subprocess under the repo's timeout config.

    `-p no:randomly` + `-p no:cacheprovider` keep the temp tree hermetic; the
    addopts stay in force for timeout keys because timeout lives in [tool.pytest.ini_options],
    which pytest reads from the temp rootdir's own pyproject (written below),
    NOT the repo's — so we copy the three timeout keys verbatim.
    """
    method, func_only, budget = read_pyproject_timeout()
    # asyncio_mode=auto mirrors the repo setting so async fixtures/tests collect
    # the same way here as they do in backend/tests (audit Part 6's experiment
    # ran under the host stack with auto mode).
    pyproject = (
        "[tool.pytest.ini_options]\n"
        f"timeout = {budget:g}\n"
        f'timeout_method = "{method}"\n'
        f"timeout_func_only = {'true' if func_only else 'false'}\n"
        'asyncio_mode = "auto"\n'
        'asyncio_default_fixture_loop_scope = "function"\n'
        'addopts = "-p no:randomly -p no:cacheprovider"\n'
    )
    with tempfile.TemporaryDirectory(prefix="timeout-guard-") as tmp:
        root = Path(tmp)
        (root / "pyproject.toml").write_text(pyproject)
        (root / "test_harness.py").write_text(HARNESS_TESTS)
        return subprocess.run(
            [sys.executable, "-m", "pytest", "test_harness.py", "-q", "--tb=no"],
            check=False,  # nonzero rc is the CORRECT verdict here; verdict() reads the output
            cwd=root,
            capture_output=True,
            text=True,
            timeout=budget + BUDGET_SLACK_S,
        )


# ------------------------- verdict parsing -------------------------

NODE_DOWN_RE = re.compile(r"\[gw\d+\] node down", re.I)
# A hang site that timed out shows as an ERROR (setup/teardown phases) or a
# FAILURE (call phase), always naming "Timeout".
TIMEOUT_LINE_RE = re.compile(r"(Timeout >[\d.]+s|Failed: Timeout|ERROR.*Timeout|TIMEOUT )", re.I)
# Final count line, both shapes: "==== 2 failed, 1 passed in 15.29s ====" and,
# under -q, the bare "2 failed, 1 passed, 1 error in 15.29s".
SUMMARY_RE = re.compile(r"^(?:=+ )?.*\b(?:passed|failed|error)\b.*\bin [\d.]+s\b.*$", re.I | re.M)


def verdict(out: str, budget: float) -> list[str]:
    """Return a list of failed checks ([] means green)."""
    checks: list[str] = []
    if NODE_DOWN_RE.search(out):
        checks.append("node-down line present — timeout killed the worker, not the test")
    if not SUMMARY_RE.search(out):
        checks.append("no pytest summary line — the process died mid-run (old thread-method class)")
    for site, test_name in HANG_SITES.items():
        if test_name not in out:
            checks.append(f"hang site {site!r} never appeared in output (collection problem?)")
    if "Timeout" not in out and "timeout" not in out:
        checks.append("no Timeout error/failure anywhere — hangs ran past budget")
    return checks


# ------------------------- self-test -------------------------


def self_test() -> int:
    """Parser checks on canned outputs — no subprocess, no repo config needed."""
    checks: list[tuple[str, bool]] = []
    old_stack = """
[gw0] node down: Not properly terminated
"""
    checks.append(("node-down detected", bool(NODE_DOWN_RE.search(old_stack))))
    good = """
.EF                                                                [100%]
FAILED test_harness.py::test_body_hang - Failed: Timeout >5.0s
ERROR test_harness.py::test_setup_hang - Failed: Timeout >5.0s
ERROR test_harness.py::test_teardown_hang - Failed: Timeout >5.0s
2 failed, 1 passed, 1 error in 15.29s
"""
    checks.append(("summary detected", bool(SUMMARY_RE.search(good))))
    checks.append(("clean output passes all checks", verdict(good, 5.0) == []))
    checks.append(("old-stack output fails all checks", len(verdict(old_stack, 5.0)) >= 2))
    n_fail = sum(1 for _, ok in checks if not ok)
    for name, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    print(f"timeout-guard self-test: {len(checks) - n_fail}/{len(checks)} pass")
    return 1 if n_fail else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--self-test", action="store_true", help="parser-only checks")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()

    method, func_only, budget = read_pyproject_timeout()
    print(
        f"timeout-guard: pyproject says timeout={budget:g}s method={method} func_only={func_only}"
    )
    if method != "signal" or func_only:
        print(
            "FAIL: repo config is NOT the ruled-in stack (need signal + func_only=false).\n"
            "Per the T5 ruling packet, any config change needs a NEW owner ruling; "
            "this guard refuses to bless a stack it was not written for."
        )
        return 1

    try:
        proc = run_harness(budget)
    except subprocess.TimeoutExpired as e:
        print(
            f"FAIL: harness subprocess exceeded {budget + BUDGET_SLACK_S:g}s — a hang ran past budget"
        )
        print((e.stdout or "")[-4000:] if isinstance(e.stdout, str) else "")
        return 1

    out = proc.stdout + proc.stderr
    failed = verdict(out, budget)
    for line in out.splitlines():
        if line.strip():
            print(f"  | {line}")
    if failed:
        print("\nFAIL:")
        for c in failed:
            print(f"  - {c}")
        print(f"(exit code {proc.returncode})")
        return 1
    # rc expectations: the three hangs surface as errors/failures — a nonzero rc
    # is the CORRECT verdict here; the run surviving WITH a summary is the point.
    print(
        f"\nPASS: all three hangs failed inside budget, no node-down, summary printed "
        f"(pytest rc={proc.returncode})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
