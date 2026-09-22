#!/usr/bin/env python3
"""Tests for the WP2.1 coverage-denominator reconciliation (docs state truth).

Run explicitly; outside testpaths:

    uv run python -m pytest scripts/test_coverage_denominator.py -q

WP2.1's defect: the repo published two "backend unit coverage" numbers ~14pp
apart (CI-merged 70.33 vs fallback-collected 84.39) and NEVER stated which
denominator each came from. P's hypothesis was validate.sh's unit+contracts+
security leg; MEASURED (2026-09-20, this WP): both sides share the exact
denominator (527 files / 78,916 statements, pyproject omit+exclude config) —
the gap is CI-side collection LOSS: run 35475023071's junit carries 718
executed cases from test_batch_aggregator/test_cleanup_service/
test_system_broadcaster while that run's combined .dat reports those files at
20.6%/18.1%/14.2% (local identical tree + CI env flags + dead Redis + xdist:
94.2%/98.2%/89.3%).

These tests pin the DOCUMENTED state (R-6: a doc that contradicts a
measurement is the bug):
  1. testing.md publishes BOTH measured figures, each with its denominator.
  2. The retired loser ("85%+" as the unit tier's current strength) is gone.
  3. The CI figure is labeled an undercount wherever the docs use it.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTING = REPO_ROOT / "docs" / "developer" / "testing.md"


def _text() -> str:
    return TESTING.read_text()


def test_both_numbers_published_with_denominators():
    t = _text()
    assert "70.3" in t, "CI-merged figure must be published (not hidden)"
    assert "84.1" in t, "local fallback figure at HEAD must be published"
    # each number must appear with what it counts — no bare percentages
    ci_ctx = t[max(0, t.index("70.3") - 400) : t.index("70.3") + 400]
    loc_ctx = t[max(0, t.index("84.1") - 400) : t.index("84.1") + 400]
    assert "undercount" in ci_ctx.lower(), "the CI number must be labeled an undercount"
    assert "fallback" in loc_ctx.lower() or "gate" in loc_ctx.lower(), (
        "the local number must say it comes from the fallback collection"
    )
    # the single shared denominator stated once, explicitly
    assert re.search(r"78,?916", t), "the shared statement denominator (78,916) must be stated"


def test_retired_loser_gone():
    t = _text()
    # The old Testing-table row claimed the unit tier was "85%+" strong — that
    # was never a measured current value; the measured value is 84.1 blended
    # (local) and 70.3 (CI, undercount). The row must not survive.
    assert not re.search(r"85%\+\s*\|", t), "unit-tier '85%+' strength row must be retired (R-6)"


# ---------------------------------------------------------------------------
# The mechanism that made the CI number an undercount (measured 2026-09-20):
# pytest-randomly (repo addopts) reseeds per PROCESS; each shard job shuffled
# differently BEFORE pytest-split sliced -> groups overlapped (1,449/6,889
# pairwise) and the run executed only 18,256/27,555 tests (66%). A fixed seed
# shared across a run's jobs makes the groups disjoint + complete (measured
# union 27,555/27,555, overlap 0). github.run_id is that seed: stable within a
# run (groups agree), different across runs (order-randomization value kept).
# ---------------------------------------------------------------------------

CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"
INTEGRATION_SHARD = REPO_ROOT / ".github" / "workflows" / "integration-shard.yml"


def _shard_pytest_blocks(path: Path) -> str:
    """The pytest invocations that carry --splits (the sharded legs)."""
    import yaml

    data = yaml.safe_load(path.read_text())
    out = []
    jobs = data.get("jobs", {})
    for job in jobs.values():
        for step in job.get("steps", []):
            run = step.get("run", "")
            if "--splits" in run:
                out.append(run)
    return "\n".join(out)


def test_sharded_pytest_pins_a_run_scoped_seed():
    for path in (CI_YML, INTEGRATION_SHARD):
        block = _shard_pytest_blocks(path)
        assert block, f"{path.name}: no --splits pytest invocation found"
        assert "--randomly-seed" in block, (
            f"{path.name}: sharded pytest must pin --randomly-seed; per-process "
            "random seeds make pytest-split groups overlap (measured: CI ran 66% "
            "of the unit tier, coverage-baseline undercounted ~14pp)"
        )
        # scoped to github.run_id: identical across the run's 4 shard jobs,
        # different next run — disjoint groups AND cross-run order variation
        assert "github.run_id" in block, (
            f"{path.name}: seed must be run-scoped (github.run_id), not a "
            "constant (freezes order forever) nor per-job (the original bug)"
        )


# ---------------------------------------------------------------------------
# WP2.2: WHAT the published number IS. coverage report --format=total with
# branch=true (pyproject) emits the BLENDED statements+branches figure —
# measured 2026-09-20 against the local merged data: total 84.12 while line
# (percent_statements) is 86.02 and branch is 76.27. So coverage-baseline.json
# alone published a number that is neither line nor branch coverage, and
# neither of THOSE was published anywhere. These tests pin that line and
# branch are published separately on every main run (unit side, into the
# baseline artifact every consumer reads) and that the root instruction file
# (AGENTS.md — CLAUDE.md was retired by owner ruling 2026-09, see that file's
# line 3) stopped claiming "85%" as the unit tier's strength.
# ---------------------------------------------------------------------------

AGENTS_MD = REPO_ROOT / "AGENTS.md"


def _step_run(path: Path, job_id: str, step_name: str) -> str:
    import yaml

    data = yaml.safe_load(path.read_text())
    for step in data["jobs"][job_id]["steps"]:
        if step.get("name") == step_name:
            return step.get("run", "")
    raise AssertionError(f"{path.name}: step {step_name!r} not found in job {job_id!r}")


def test_unit_combine_publishes_line_branch_and_blended():
    run = _step_run(CI_YML, "unit-tests-coverage-merge", "Combine and check coverage threshold")
    # the json report is the only source of the three figures
    assert "coverage json" in run, (
        "combine step must emit a coverage json report (line/branch totals)"
    )
    assert "--fail-under=0" in run, (
        "json extraction must not inherit pyproject fail_under=85: exiting 1 on the "
        "extraction path reddens the job exactly when coverage moves (WP0.9 doctrine)"
    )
    for field in ("percent_statements", "percent_branches", "percent_covered"):
        assert field in run, (
            f"baseline json must carry {field} (line / branch / blended, all three)"
        )


def test_baseline_json_shape_is_read_by_the_gate():
    # WP0.6 bug class (reader/writer drift = silent skip): the richer WP2.2
    # baseline must stay legible to BOTH consumers of the flat key —
    # check-test-coverage-gate.py's _read_percent/_base_percent_from_git
    # (JSON parse of the top-level percent_covered) and test-coverage-gate.yml's
    # fetch. Adding siblings is fine; renaming or nesting the flat key would
    # break the diff gate silently, so pin writer and reader in one test.
    writer = _step_run(CI_YML, "unit-tests-coverage-merge", "Combine and check coverage threshold")
    assert re.search(r'"percent_covered"\s*:', writer), (
        "ci.yml must write percent_covered as a TOP-LEVEL quoted JSON key — the "
        "gate parses it flat; only ADD siblings (line/branch), never move it"
    )
    gate = (REPO_ROOT / "scripts" / "check-test-coverage-gate.py").read_text()
    assert 'get("percent_covered")' in gate, (
        "the gate reads the flat top-level percent_covered; if the baseline shape "
        "changes, fix BOTH sides in one commit (WP0.6 drift class)"
    )


def test_integration_combine_reports_line_and_branch():
    run = _step_run(CI_YML, "integration-coverage-merge", "Combine integration coverage")
    for field in ("percent_statements", "percent_branches"):
        assert field in run, (
            f"integration summary must publish {field} (blended-only reporting is WP2.2's defect)"
        )


def test_agents_md_carries_measured_strength_not_85():
    t = AGENTS_MD.read_text()
    assert not re.search(r"Backend Unit\s*\|\s*85%", t), (
        "AGENTS.md's Backend Unit row must not lead with 85%: measured strength is "
        "84.12 blended / 86.02 line / 76.27 branch (docs/developer/testing.md WP2.1 section)"
    )
    assert "84.12" in t and "86.02" in t and "76.27" in t, (
        "AGENTS.md must carry the measured triple (blended/line/branch), not a stale round number"
    )
