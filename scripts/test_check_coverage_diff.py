#!/usr/bin/env python3
"""Tests for check_coverage_diff in scripts/check-test-coverage-gate.py (WP0.9).

Run explicitly; outside testpaths:

    uv run python -m pytest scripts/test_check_coverage_diff.py -q

WP0.9 invariant: the gate must detect a coverage DROP against a base. The
pre-WP0.9 function never diffed against anything — it returned
(True, "Current coverage: X%") for every input, so a PR that deleted every
test could not be caught by it (spec §toothless-gates: "a misleading name is
the actual defect"). These fixtures pin the real contract:

  current percent  <- coverage.json (--cov-report=json), or COVERAGE_JSON env,
                      or an ABSENT file = genuine skip (CI where coverage was
                      never collected).
  base percent     <- COVERAGE_BASE_JSON env, else the committed
                      coverage-baseline.json at the base ref (git show), else
                      genuine skip.
  verdict          <- any drop is failure (a PR that drops coverage fails —
                      plan WP0.9 done-when); equal or increase passes.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "check-test-coverage-gate.py"


def write_coverage_json(path: Path, percent: float) -> None:
    path.write_text(json.dumps({"totals": {"percent_covered": percent}}))


@pytest.fixture()
def isolated_cwd(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COVERAGE_JSON", raising=False)
    monkeypatch.delenv("COVERAGE_BASE_JSON", raising=False)
    return tmp_path


def get_diff_fn():
    import importlib.util

    spec = importlib.util.spec_from_file_location("ctcg", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.check_coverage_diff


# ---------------------------------------------------------------------------
# The toothless-path regression: these all passed unconditionally pre-WP0.9.
# ---------------------------------------------------------------------------


def test_coverage_drop_fails(isolated_cwd, monkeypatch):
    """A drop against the base is a FAILURE — the case the old code could not see."""
    write_coverage_json(isolated_cwd / "coverage.json", 84.0)
    base = isolated_cwd / "base.json"
    write_coverage_json(base, 87.9)
    monkeypatch.setenv("COVERAGE_BASE_JSON", str(base))

    ok, msg = get_diff_fn()()
    assert ok is False, f"a coverage drop passed the diff gate: {msg}"
    assert "84.0" in msg and "87.9" in msg, f"message must name both numbers: {msg}"


def test_coverage_equal_passes(isolated_cwd, monkeypatch):
    write_coverage_json(isolated_cwd / "coverage.json", 87.9)
    base = isolated_cwd / "base.json"
    write_coverage_json(base, 87.9)
    monkeypatch.setenv("COVERAGE_BASE_JSON", str(base))

    ok, msg = get_diff_fn()()
    assert ok is True, msg


def test_coverage_increase_passes(isolated_cwd, monkeypatch):
    write_coverage_json(isolated_cwd / "coverage.json", 91.0)
    base = isolated_cwd / "base.json"
    write_coverage_json(base, 87.9)
    monkeypatch.setenv("COVERAGE_BASE_JSON", str(base))

    ok, msg = get_diff_fn()()
    assert ok is True, msg


# ---------------------------------------------------------------------------
# Skip semantics: genuinely-absent data must not fake a pass, but must not
# block CI where coverage was never collected.
# ---------------------------------------------------------------------------


def test_no_current_coverage_skips(isolated_cwd, monkeypatch):
    base = isolated_cwd / "base.json"
    write_coverage_json(base, 87.9)
    monkeypatch.setenv("COVERAGE_BASE_JSON", str(base))
    # Seam explicitly points at a report that was never produced: CI where
    # coverage was never collected. Honest skip, not a faked pass.
    monkeypatch.setenv("COVERAGE_JSON", str(isolated_cwd / "missing-coverage.json"))
    ok, msg = get_diff_fn()()
    assert ok is True
    assert "skip" in msg.lower()


def test_no_base_available_skips(isolated_cwd):
    write_coverage_json(isolated_cwd / "coverage.json", 1.0)
    ok, msg = get_diff_fn()()
    assert ok is True
    assert "skip" in msg.lower()


@pytest.mark.timeout(300)  # the FIXED path is milliseconds; on regression this
# case actually launches the full-suite collection (90-120s) to prove the old
# ordering pays it — needs headroom to fail on the wall assertion, not the
# tier timeout.
def test_unresolvable_base_skips_before_collecting(isolated_cwd):
    """Base-first ordering (WP0.9 follow-up): with NO seam at all, an
    unresolvable base must skip WITHOUT attempting the 90s+ inline collection.
    The pre-fix order collected first (and in this scratch tree collection
    cannot even work — the old code surfaced a collection-failure FAIL where
    the honest answer is a skip; the first real-world occurrence burned 93.6s
    in a pre-push hook to then skip anyway)."""
    import time

    t0 = time.monotonic()
    ok, msg = get_diff_fn()(base_branch="nonexistent-base-xyz")
    elapsed = time.monotonic() - t0
    assert ok is True, f"unresolvable base must skip, not fail: {msg}"
    assert "skip" in msg.lower(), msg
    assert elapsed < 5.0, f"skipped but only AFTER attempting collection ({elapsed:.1f}s)"


# ---------------------------------------------------------------------------
# The git-shipped baseline: what CI actually uses. A committed
# coverage-baseline.json at the base ref is the source of truth without
# re-running the suite on base.
# ---------------------------------------------------------------------------


def test_baseline_from_git_ref(isolated_cwd):
    subprocess.run(["git", "init", "-q"], cwd=isolated_cwd, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=isolated_cwd, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=isolated_cwd, check=True)
    baseline = {"percent_covered": 87.9, "source": "test"}
    (isolated_cwd / "coverage-baseline.json").write_text(json.dumps(baseline))
    subprocess.run(["git", "add", "coverage-baseline.json"], cwd=isolated_cwd, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=isolated_cwd, check=True)

    write_coverage_json(isolated_cwd / "coverage.json", 80.0)
    ok, msg = get_diff_fn()(base_branch="HEAD")
    assert ok is False, f"drop vs git-shipped baseline passed: {msg}"


# ---------------------------------------------------------------------------
# CLI wiring: the exit code the CI step sees.
# ---------------------------------------------------------------------------


def test_cli_exit_code_on_drop(isolated_cwd, monkeypatch):
    """The whole script must exit non-zero when the diff fails."""
    write_coverage_json(isolated_cwd / "coverage.json", 50.0)
    monkeypatch.setenv("COVERAGE_JSON", str(isolated_cwd / "coverage.json"))
    base = isolated_cwd / "base.json"
    write_coverage_json(base, 87.9)
    monkeypatch.setenv("COVERAGE_BASE_JSON", str(base))
    subprocess.run(["git", "init", "-q"], cwd=isolated_cwd, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=isolated_cwd, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=isolated_cwd, check=True)
    subprocess.run(
        ["git", "commit", "-q", "--allow-empty", "-m", "base"], cwd=isolated_cwd, check=True
    )

    r = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--base-branch", "HEAD"],
        capture_output=True,
        text=True,
        cwd=isolated_cwd,
        check=False,
    )
    assert r.returncode == 1, f"drop through the CLI did not fail the step: {r.stdout[-300:]}"
    # Must be the DROP verdict, not the collection-failure branch — the two
    # paths share an exit code and only one is the gate's point.
    assert "DROPPED" in r.stdout, f"CLI failed for the wrong reason: {r.stdout[-300:]}"
