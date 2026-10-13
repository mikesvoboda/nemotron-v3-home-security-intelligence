"""WP2.5 red-first: the coverage verdicts must sit inside ci-gate's needs:.

AUDIT-FINDINGS.md §2.1 (verified independently): branch protection requires
exactly one status context, `CI Gate (Required Checks)`, and the three
coverage-merge jobs that compute the WP2.3 floors were UNREACHABLE from
ci-gate's transitive `needs:` closure — the floors computed, published, and
stopped nothing. A gate that computes a verdict no required job consumes is
the same failure mode as a swallowed run step: signal produced, never acted
on.

This test IS the required reachability walk, pinned as an invariant:

  * the three coverage-verdict jobs must be in ci-gate's closure;
  * ci-gate must treat their FAILURE as blocking (check_job lines — skipped
    passing is by design, the detect-changes skip paths);
  * the walk must also prove the invariant's own teeth: an invented job
    outside the closure is reported unreachable (a vacuous walker that says
    "reachable" for everything would pass the first assertion for the wrong
    reason).
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Any

import yaml

CI_YML = Path(".github/workflows/ci.yml")

# The jobs that turn coverage data into a verdict. If any drifts out of the
# required closure, the floors are decorative again.
COVERAGE_VERDICT_JOBS = {
    "unit-tests-coverage-merge",
    "integration-coverage-merge",
    "frontend-coverage-merge",
}


def _needs_of(job: dict[str, Any]) -> list[str]:
    needs = job.get("needs", [])
    if isinstance(needs, dict):
        return list(needs)
    return list(needs)


def closure_from(jobs: dict[str, Any], root: str) -> set[str]:
    """Transitive `needs:` closure of root (exclusive of root itself)."""
    seen: set[str] = set()
    stack = list(_needs_of(jobs[root]))
    while stack:
        name = stack.pop()
        if name in seen or name not in jobs:
            continue
        seen.add(name)
        stack += _needs_of(jobs[name])
    return seen


def _load() -> dict[str, Any]:
    return yaml.safe_load(CI_YML.read_text())


class _CiYml:
    """Shared load: every class walks the same workflow file."""

    def setup_method(self) -> None:
        self.wf = _load()
        self.jobs = self.wf["jobs"]


class TestCoverageVerdictsReachable(_CiYml):
    def setup_method(self) -> None:
        super().setup_method()
        self.closure = closure_from(self.jobs, "ci-gate")

    def test_coverage_verdict_jobs_are_in_the_required_closure(self) -> None:
        missing = COVERAGE_VERDICT_JOBS - self.closure
        assert not missing, (
            f"{sorted(missing)} compute coverage floors but ci-gate "
            f"(the ONLY required status context) cannot see them — floors "
            f"would be computed, not enforced (AUDIT §2.1 regression)"
        )

    def test_ci_gate_verdicts_on_their_results(self) -> None:
        """Reachable via `needs:` is necessary; ci-gate must also consume
        their RESULT — a needs: edge plus no check_job line still green-lights
        a failed floor."""
        gate_run = "\n".join(
            step.get("run", "") for step in self.jobs["ci-gate"]["steps"] if step.get("run")
        )
        for job in sorted(COVERAGE_VERDICT_JOBS):
            assert f"needs.{job}.result" in gate_run, (
                f"ci-gate does not check {job}.result — its failure would "
                "not flip the required context"
            )

    def test_walker_has_teeth_on_a_synthetic_graph(self) -> None:
        # self-check: closure_from must distinguish, not say "reachable" for
        # everything (a walker returning set(jobs.keys()) passes the first
        # assertion for the wrong reason)
        synthetic = {
            "root": {"needs": ["mid"]},
            "mid": {"needs": ["leaf"]},
            "leaf": {},
            "island": {"needs": ["root"]},
        }
        assert closure_from(synthetic, "root") == {"mid", "leaf"}
        # needs: as a mapping (GitHub's name->required-form) must also walk
        assert closure_from(
            {"root": {"needs": {"mid": {"required": True}}}, "mid": {}}, "root"
        ) == {"mid"}


class TestCiGateIfContract(_CiYml):
    def test_gate_runs_always_so_needs_can_read_skipped(self) -> None:
        # Adding needs: edges only enforces if ci-gate itself still runs when
        # upstream jobs skip/fail (if: always()); without it the whole gate
        # would skip and the required context would report nothing at all.
        assert self.jobs["ci-gate"].get("if") == "always()"


class TestWalkOnRealData(_CiYml):
    def test_gate_direct_needs_count_is_reported(self) -> None:
        direct = _needs_of(self.jobs["ci-gate"])
        # adding 3 edges is the fix; the count must not silently balloon
        assert len(direct) <= 30, f"ci-gate has {len(direct)} direct needs — review"


class TestRunStepCommentSwallow(_CiYml):
    """The anti-rot class invariant (AUDIT §7.4): a folded `run:` scalar with
    '#' comment lines swallows every suite after the first comment."""

    def test_no_folded_step_loses_argv_to_a_comment(self) -> None:
        offenders = []
        for jname, job in self.jobs.items():
            for step in job.get("steps", []) or []:
                run = step.get("run") or ""
                # a step that lists pytest files AND contains a comment line
                # mid-argv is the swallow shape (post-collapse, folded
                # scalars arrive here already newline-stripped)
                if re.search(r"\.py\s+#", run) and "pytest" in run:
                    offenders.append(f"{jname}: {step.get('name')}")
        assert offenders == [], f"folded run: steps with inline # swallow argv: {offenders}"

    def test_antrot_step_names_all_gate_suites(self) -> None:
        step_runs = [
            step.get("run", "")
            for job in self.jobs.values()
            for step in job.get("steps", []) or []
            if step.get("run")
        ]
        joined = "\n".join(step_runs)
        for suite in (
            "scripts/test_autospec_sweep.py",
            "scripts/test_check_mock_spec.py",
            "scripts/test_mutation_score.py",
            "scripts/test_check_ai_provider_parity.py",
            # W1.1: the AGENTS.md ratchet's real-tree green assertion lives
            # in this suite — dropping it from the step silently un-teeths
            # the gate (agents-md.yml itself gates nothing).
            "scripts/test_agents_md_validator.py",
        ):
            assert suite in joined, f"{suite} dropped from the anti-rot CI step"


class TestAntiRotBatteryHasAFloor(_CiYml):
    """A FLOOR ratchet on the anti-rot battery, sibling to the direct-needs cap
    in ``TestWalkOnRealData``.

    WHY A FLOOR AND NOT A SET. The silent mutant in this file's own class is not
    deleting a suite's file — pytest reddens that loudly (measured: `-n 8`
    xdist rc=5 "no tests ran", serial rc=4 "file or directory not found", and
    the step has no `||`/`tee`/`continue-on-error` to absorb either). The silent
    one is dropping the PATH FROM ARGV while the file stays on disk: nothing in
    the repo reddens, because `test_reachability.py`'s entries-pin deliberately
    scans non-test script paths only. A literal set would teeth that but
    false-reds on every merge that adds a gate, so it is not shippable; a floor
    teeths any count-reducing edit and names no path, so a merge that ADDS one
    (this very commit: 32 -> 33) stays green.

    33 is measured, not estimated: `shlex.split` over this step's `run:` counts
    32 `.py` paths at `2079e4a21` (the live main this branch cut from) plus the
    one path this branch adds. Raising it is a one-line reviewed edit in the
    commit that adds a suite; lowering it must come with a reason.

    The lookup is pinned to a JOB, not just a step name: the step is collected
    from `collection-sanity` only, so a later edit that gives another job a
    step of the same name reddens THAT job's owner rather than silently
    comparing the wrong `run:`. The sibling name-pin above has no job identity
    to share — it joins every `run:` in the file and substring-searches — so
    this test states its scope explicitly instead of converging on one.
    """

    ANTIROT_JOB = "collection-sanity"
    ANTIROT_STEP = "Run the anti-rot gates' own tests"

    def test_antirot_battery_keeps_at_least_its_suite_floor(self) -> None:
        job = self.jobs.get(self.ANTIROT_JOB)
        assert job is not None, (
            f"job {self.ANTIROT_JOB!r} is gone from ci.yml — the anti-rot "
            "battery it carries would go unwatched; update this test with the "
            "rename."
        )
        runs = [
            step.get("run", "")
            for step in job.get("steps", []) or []
            if step.get("name") == self.ANTIROT_STEP
        ]
        assert len(runs) == 1, (
            f"expected exactly one {self.ANTIROT_STEP!r} step inside job "
            f"{self.ANTIROT_JOB!r}, found {len(runs)}"
        )
        paths = [a for a in shlex.split(runs[0]) if a.endswith(".py")]
        assert paths, f"{self.ANTIROT_STEP} yielded no .py argv — parse failure, not a pass"
        assert len(paths) >= 33, (
            f"anti-rot battery holds {len(paths)} suites, floor is 33 — a suite "
            "left the battery. A missing FILE already reddens pytest; a dropped "
            "ARGV entry is invisible, which is what this floor is for."
        )
