#!/usr/bin/env python3
"""WP2.3: floors at measured values, and the nightly gate reports coverage
failures ONLY for coverage reasons.

Run explicitly; outside testpaths:

    uv run python -m pytest scripts/test_coverage_floors.py -q

Two defects pinned here (plan P WP2.3):

1. THE MISATTRIBUTED RED. `nightly-full-gate.yml`'s combined-coverage step
   carries `if: always()`, so when a tier step fails (or is cancelled and
   its data file never lands), `coverage combine` dies on the missing data
   file / stale combined file and the step reddens WITH A COVERAGE MESSAGE
   — P measured 3 of the last 4 nightly failures were this: red labeled
   "coverage" for reasons that were not coverage. Same class as the
   collection-failed false positive WP0.9 logged. Fix pinned here: the gate
   runs only when BOTH tier steps succeeded (full-execution data — the only
   enforceable measurement) AND both data files exist; otherwise it SKIPS
   saying exactly which tier's absence it is.

2. FLOOR HYGIENE (R-1). Backend integration floor 37 and frontend floors
   80/74.6/78.4/80.9 are the MEASURED values (runs fetched 2026-09-20; the
   frontend declared 83/77/81/84 sat above every observed run — a floor that
   never held). The merge step enforces the frontend floors only when all
   shards passed, so a red shard can't launder a false coverage FAIL either.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"
NIGHTLY = REPO_ROOT / ".github" / "workflows" / "nightly-full-gate.yml"

# The step body's path prefix, rewritten to tmp_path in the E2Es below. It is
# a search pattern only — this sandbox never creates or touches it.
RUNNER_COV_DIR = "/tmp/fcl-cov"  # noqa: S108 - ported literal, never touched


def _job_step(path: Path, job_id: str, needle: str) -> dict:
    data = yaml.safe_load(path.read_text())
    for step in data["jobs"][job_id]["steps"]:
        if needle in step.get("name", ""):
            return step
    raise AssertionError(f"{path.name}: no step matching {needle!r} in job {job_id!r}")


# ---------------------------------------------------------------------------
# Defect 1: the nightly combined-coverage gate.
# ---------------------------------------------------------------------------


def test_nightly_gate_only_verdicts_on_full_data():
    gate = _job_step(NIGHTLY, "backend-full", "Combined coverage gate")
    tier_ids = [
        s.get("id")
        for s in yaml.safe_load(NIGHTLY.read_text())["jobs"]["backend-full"]["steps"]
        if "tier (validate.sh semantics)" in s.get("name", "")
    ]
    assert all(tier_ids), (
        "both nightly tier steps must carry step ids (the gate reads their outcomes)"
    )
    cond = (gate.get("if") or "").replace("\n", " ")
    for tid in tier_ids:
        assert (
            f"steps.{tid}.outcome == 'success'" in cond
            or f'steps.{tid}.outcome == "success"' in cond
        ), (
            f"the combined gate must require tier step {tid} to have SUCCEEDED: "
            "gate data from a failed tier is partial-execution data, and a floor "
            "verdict on it is a test failure wearing a coverage costume"
        )
    body = gate.get("run", "")
    assert ".coverage.unit" in body and ".coverage.integration" in body, (
        "gate still combines both files"
    )
    assert "-f " in body or "-f\t" in body, "gate must check both data files exist before combining"
    assert "--fail-under=80" in body, (
        "the 80% combined floor is unchanged (R-1: this floor already holds)"
    )


@pytest.mark.timeout(120)  # mints real coverage data from a SCRATCH pytest
# project (~3s — hermetic: no repo tests, no services, runs in any CI job).
def test_nightly_gate_body_skips_on_missing_data(tmp_path):
    """EXECUTE the committed step body with only ONE data file present.
    It must exit 0 with a skip that names the missing tier — and must not
    print a coverage-failure verdict. Reproduced before the fix: combine rc=1
    'Couldn't combine from non-existent path .coverage.integration', and a
    stale combined file made `report --fail-under=80` print 'Coverage failure:
    total of 25.04 is less than fail-under=80.00' — the misattributed red."""
    body = _job_step(NIGHTLY, "backend-full", "Combined coverage gate")["run"]
    # Port the runner's commands to this sandbox: `uv run python` -> this
    # interpreter; /tmp/fcl-cov -> tmp_path. Logic untouched.
    body = body.replace("uv run python", sys.executable).replace(RUNNER_COV_DIR, str(tmp_path))
    cov = tmp_path / ".coverage.unit"
    _mint_partial_coverage(tmp_path, cov)
    env = {**os.environ, "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md")}
    proc = subprocess.run(
        ["bash", "-c", body],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,  # the RETURN CODE is the assertion's subject
    )
    combined = proc.stdout + proc.stderr
    assert proc.returncode == 0, (
        f"missing integration data must SKIP (rc 0), not verdict coverage: rc={proc.returncode}\n{combined[-500:]}"
    )
    assert "skip" in combined.lower() and "integration" in combined.lower(), (
        f"the skip must say WHICH tier's data is absent: {combined[-300:]}"
    )
    assert "coverage failure" not in combined.lower(), (
        f"a non-coverage absence must not print a coverage verdict: {combined[-300:]}"
    )


def _mint_partial_coverage(scratch: Path, data_file: Path) -> None:
    """A ~50%-covered synthetic module under a throwaway pytest project.

    Deliberately NOT the repo's suite: the anti-rot job that runs this file
    has no Postgres/Redis services, and the whole point of these E2Es is the
    STEP BODY's combine/report/skip logic — which any real .coverage exercises
    identically. Two functions, one called: report lands under the 80 floor.
    """
    proj = scratch / "proj"
    proj.mkdir(exist_ok=True)
    (proj / "mod.py").write_text("def a():\n    return 1\n\n\ndef b():\n    return 2\n")
    (proj / "test_mod.py").write_text("from mod import a\n\n\ndef test_a():\n    assert a() == 1\n")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "test_mod.py",
            "-q",
            "-p",
            "no:randomly",
            "-p",
            "no:cacheprovider",
            "-o",
            "addopts=",
            "--cov=mod",
            "--cov-report=",
            "--cov-fail-under=0",
        ],
        cwd=proj,
        env={**os.environ, "COVERAGE_FILE": str(data_file)},
        check=True,
        capture_output=True,
    )


@pytest.mark.timeout(120)  # mints two coverage files, body is ms.
def test_nightly_gate_body_still_enforces_on_complete_data(tmp_path):
    """The skip must not launder the real check: with BOTH data files
    present, the same body must run combine + report, and below-80 must be
    a non-zero exit naming the floor."""
    body = _job_step(NIGHTLY, "backend-full", "Combined coverage gate")["run"]
    body = body.replace("uv run python", sys.executable).replace(RUNNER_COV_DIR, str(tmp_path))
    unit = tmp_path / ".coverage.unit"
    _mint_partial_coverage(tmp_path, unit)
    shutil.copy(unit, tmp_path / ".coverage.integration")  # second tier's data, present
    env = {**os.environ, "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md")}
    proc = subprocess.run(
        ["bash", "-c", body],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,  # the RETURN CODE is the assertion's subject
    )
    combined = proc.stdout + proc.stderr
    assert proc.returncode != 0, (
        f"security-tier-only data (~25%) under the 80 floor must exit non-zero: {combined[-400:]}"
    )
    assert "80" in combined or "fail-under" in combined.lower(), "the failure must name the floor"


# ---------------------------------------------------------------------------
# Defect 2 (frontend): floors measured + enforced, and ONLY on complete data.
# ---------------------------------------------------------------------------


def test_frontend_merge_enforces_floors_only_when_shards_passed():
    merge = _job_step(CI_YML, "frontend-coverage-merge", "Merge frontend coverage")
    body = merge["run"]
    assert "--enforce" in body, (
        "the merge step must enforce the four floors (R-7: advisory -> blocking)"
    )
    assert "needs.frontend-tests.result" in body, (
        "enforcement must be gated on all shards having passed: partial shard data "
        "under a floor is a test failure wearing a coverage costume (same class "
        "as the nightly defect pinned above)"
    )


def test_frontend_floor_numbers_are_the_measured_ones():
    vite = (REPO_ROOT / "frontend" / "vite.config.ts").read_text()
    import re

    block = re.search(r"thresholds:\s*\{([^}]*)\}", vite)
    assert block, "vite.config.ts coverage thresholds block must exist"
    vals = dict(re.findall(r"(statements|branches|functions|lines):\s*([0-9.]+)", block.group(1)))
    measured = {"statements": "80", "branches": "74.6", "functions": "78.4", "lines": "80.9"}
    for k, v in measured.items():
        assert float(vals[k]) == float(v), (
            f"frontend floor {k} must be the measured {v} (run 35486259345); the "
            "declared 83/77/81/84 above every observed run is not a floor (R-1)"
        )


# ---------------------------------------------------------------------------
# Backend absolute floors (R-1): wired INTO the merge steps that mint the
# measurement — unit 70 (baseline lineage 70.32 published by run 2ab66ff1;
# rises to ~84 once WP2.1's seed fix reaches main), integration 37 (merged
# percent=37.01 from run 35486259345's integration-coverage-merge). Before
# WP2.3 the merges extracted the number and enforced nothing: the ONLY
# absolute floor that executed anywhere was nightly's 80 combined.
# Same completeness guard as frontend: enforce only when the tier actually
# passed — partial data is not a coverage verdict.
# ---------------------------------------------------------------------------


def test_unit_merge_enforces_absolute_floor_70():
    merge = _job_step(CI_YML, "unit-tests-coverage-merge", "Combine and check coverage threshold")
    body = merge["run"]
    assert "needs.unit-tests.result" in body, (
        "the unit floor must only be judged on a PASSED tier: partial shard data "
        "under a floor is not a coverage verdict (WP2.3 class)"
    )
    assert "FLOOR" in body and "70" in body, (
        "unit merged coverage carries an absolute floor of 70 = the measured "
        "published baseline lineage (70.32 -> rounds down); R-1 floors at measured"
    )


def test_integration_merge_enforces_floor_37():
    merge = _job_step(CI_YML, "integration-coverage-merge", "Combine integration coverage")
    body = merge["run"]
    assert "integration-tests-api.result" in body, (
        "integration floors gate on the shards having passed (completeness guard)"
    )
    assert "FLOOR" in body and "37" in body, (
        "integration merged coverage carries an absolute floor of 37 = the "
        "measured merged percent (37.01, run 35486259345); R-1 floors at measured"
    )
