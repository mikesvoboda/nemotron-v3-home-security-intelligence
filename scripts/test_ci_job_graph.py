#!/usr/bin/env python3
"""Gate test for ci.yml's job graph (WP0.6) — run explicitly; outside testpaths.

    uv run python scripts/test_ci_job_graph.py

WP0.6 invariant: a job either gates merges (reachable from ci-gate) or it does
not exist in a state where its red is ignorable. Historical harm this pins:
main's four red jobs (Trivy x2 / Dead Code / Test Performance Audit) sat OUTSIDE
ci-gate's reach while `CI Gate` reported SUCCESS — the same invisibility class
that hid WP0.2's CVEs for six months.

Classes that satisfy the invariant:
  GATE    reachable from ci-gate transitively (verdict converges in ci-gate)
  PLUMB   artifact-only job that cannot produce a correctness verdict
          (coverage merge/upload) — enumerated by name below, additions FAIL
  TRIAGE  jobs whose red is ACTIONED at runtime: they carry their own
          "Create Linear issue on failure" step, or run schedule/dispatch-only
          (a nightly red is triaged, not merge-ignorable)
  NEVER-RED jobs that structurally cannot fail (advisory summary writers) — the
          graph test treats a job with no failing exit path as advisory-only;
          they're allowed but must stay non-verdict.
Every other job MUST be GATE-reachable. A new job that is red-able, not gated,
not triaged, and not plumbing -> FAIL here.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CI = ROOT / ".github" / "workflows" / "ci.yml"

# Artifact plumbing — cannot produce a verdict; keep this list honest and short.
PLUMBING = {
    "unit-tests-coverage-merge",
    "integration-coverage-merge",
    "frontend-coverage-merge",
}

SCHEDULE_ONLY_MARKERS = ("schedule", "workflow_dispatch")


def job_needs(job: dict) -> list[str]:
    n = job.get("needs", [])
    return n if isinstance(n, list) else [n]


def has_linear_triage(job: dict) -> bool:
    return any("Linear" in (s.get("name") or "") for s in job.get("steps", []))


def schedule_only(job: dict) -> bool:
    cond = str(job.get("if", ""))
    if not cond:
        return False
    return (
        "github.event_name == 'schedule'" in cond
        and "pull_request" not in cond
        and "push" not in cond
    )


def main() -> int:
    d = yaml.safe_load(CI.read_text())
    jobs = d["jobs"]
    if "ci-gate" not in jobs:
        print("FAIL: ci-gate job vanished from ci.yml", file=sys.stderr)
        return 1

    gate_needs = job_needs(jobs["ci-gate"])
    reach: set[str] = set()
    stack = list(gate_needs)
    while stack:
        j = stack.pop()
        if j in reach or j not in jobs:
            continue
        reach.add(j)
        stack.extend(job_needs(jobs[j]))

    failures: list[str] = []

    # 1. Every job lands in an allowed class.
    for name, cfg in jobs.items():
        if name == "ci-gate":
            continue
        if name in reach or name in PLUMBING:
            continue
        if has_linear_triage(cfg) or schedule_only(cfg):
            continue
        cond = str(cfg.get("if", ""))[:60].replace("\n", " ")
        failures.append(
            f"job {name!r} can go red on PR/push yet converges nowhere: "
            f"not in ci-gate's reach, no Linear-triage step, not schedule-only "
            f"(if={cond!r}) — promote it to the gate or delete it (WP0.6)"
        )

    # 2. ci-gate's check_job lines must cover its direct needs exactly —
    #    a gated job nobody checks, or a checked job not actually needed, is
    #    the same conclusion-vs-verdict lie in a new costume.
    gate_script = "\n".join(
        s.get("run", "") for s in jobs["ci-gate"].get("steps", []) if s.get("run")
    )
    import re

    checked = set(
        re.findall(r'check_job\s+"[^"]+"\s+"\$\{\{\s*needs\.([a-zA-Z0-9_-]+)\.result', gate_script)
    )
    gateable = {n for n in gate_needs if n not in ("detect-changes",)}
    missing = gateable - checked
    extra = checked - set(gate_needs)
    if missing:
        failures.append(f"ci-gate needs but never check_job()s: {sorted(missing)}")
    if extra:
        failures.append(f"ci-gate check_job()s a job it does not need: {sorted(extra)}")

    # 3. Plumbing list must match reality (renames force an explicit edit here).
    for name in PLUMBING:
        if name not in jobs:
            failures.append(f"plumbing job {name!r} no longer exists — update this test's list")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1

    print(
        f"OK: every ci.yml job is gated, triaged, or plumbing ({len(jobs)} jobs, gate reaches {len(reach)})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
