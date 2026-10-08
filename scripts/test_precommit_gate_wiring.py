#!/usr/bin/env python3
"""Gate test for the pre-commit hooks job (O1.12/UR-37) — run explicitly; outside testpaths.

    uv run python scripts/test_precommit_gate_wiring.py

O1.12 invariant: the repository's pinned pre-commit hooks run inside the required
gate on every PR. Before this package the gate ran only part of them (ruff+radon
in `lint`), so a PR could pass every required check and still block every later
push that touched its files — the 2026-10-08 class: #6888 (semgrep), #6890
(slow-test guard), #6891, #6892 all post-merge fixes for exactly this.

What this pins (fixture-first: every clause FAILS on main's ci.yml today, which
is precisely the defect):
  1. a dedicated `precommit-hooks` job exists (own job = the ci.yml hot-file rule),
  2. it runs the committed `.pre-commit-config.yaml` over the PR's changed files
     (`pre-commit run --from-ref ... --to-ref ...`), not a hand-picked subset,
  3. it is wired into `ci-gate` the only way that carries a red (direct need +
     check_job line — scripts/test_ci_job_graph.py's WP0.6 doctrine),
  4. the job carries the B1.3-class self-test: it must prove the hooks it runs
     actually catch a credential-shaped fixture (the #6888 class), so a broken
     or hollow job cannot report green.

It deliberately does NOT re-check the WP0.6 graph membership — that stays in
test_ci_job_graph.py; this file checks the job's existence and CONTENT, which
the graph test cannot see.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CI = ROOT / ".github" / "workflows" / "ci.yml"

JOB = "precommit-hooks"


def main() -> int:
    d = yaml.safe_load(CI.read_text())
    jobs = d["jobs"]

    failures: list[str] = []

    # 1. The job exists.
    if JOB not in jobs:
        print(
            f"FAIL: job {JOB!r} missing from ci.yml — the hooks do not run in the "
            "required gate (O1.12/UR-37). The 2026-10-08 record: #6888/#6890/#6891/"
            "#6892 were push-blocking rot that today's gate could not see.",
            file=sys.stderr,
        )
        return 1

    job = jobs[JOB]
    script = "\n".join(
        s.get("run", "") for s in job.get("steps", []) if s.get("run")
    )

    # 2. It runs the committed config over the changed-file range.
    if "pre-commit run" not in script:
        failures.append(f"job {JOB!r} does not invoke `pre-commit run`")
    if "--from-ref" not in script or "--to-ref" not in script:
        failures.append(
            f"job {JOB!r} must run the range form (`--from-ref ... --to-ref ...`) "
            "so it checks the PR's changed files the same way a push does"
        )

    # 3. Wired into ci-gate the WP0.6 way. (test_ci_job_graph.py enforces the
    #    same shape generally; this names it for the O1.12 Done-when.)
    gate = jobs.get("ci-gate", {})
    gate_needs = gate.get("needs", [])
    gate_needs = gate_needs if isinstance(gate_needs, list) else [gate_needs]
    if JOB not in gate_needs:
        failures.append(f"ci-gate does not need {JOB!r}")
    gate_script = "\n".join(
        s.get("run", "") for s in gate.get("steps", []) if s.get("run")
    )
    if f"needs.{JOB}.result" not in gate_script:
        failures.append(f"ci-gate carries no check_job line for needs.{JOB}.result")

    # 4. The B1.3-class self-test is part of the job (a fixture that must trip
    #    the hooks; the job fails if its own hooks fail to catch it).
    if "self-test" not in script.lower():
        failures.append(
            f"job {JOB!r} has no B1.3-class self-test step — a job that silently "
            "skips every hook would report green (O1.12 Done-when: fails on the fixture)"
        )

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1

    print(f"OK: pre-commit hooks job exists, ranges over changed files, gates, and self-tests ({JOB})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
