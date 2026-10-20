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
        # 30 -> 31 adjudicated in the DOCS-NJT commit that pressed it: the
        # negative-tooling-claims gate moved into ci.yml as its OWN job per the
        # hot-file rule UR-121 (rules.md; by rule id, never by line — rules.md
        # renumbers with every ruling),
        # and a direct need is the only
        # edge WP0.6 accepts for a red-able job — a bare `needs:` an
        # intermediate never reads carries no red (see result_checked_needs in
        # test_ci_job_graph.py). Same doctrine as the suppression ratchet: a
        # rise moves here, in the reviewed commit that causes it, never silently.
        #
        # 31 -> 32 adjudicated here, in the [r149e] commit that causes it: that
        # package orders a `tsc --noEmit` step over frontend/tests/golden/ and
        # UR-121 forbids adding a STEP to the shared frontend-typecheck job
        # (its only permitted edit is one appended entry to a list a step
        # already reads, and `npm run typecheck` is a `run:` command, not a list
        # item), so the check arrives as its own job — frontend-golden-typecheck
        # — and WP0.6 then REQUIRES the direct need. The rise is compelled by
        # the two rules together, not discretionary: decline either one and the
        # package's Done-when ("the type-check step runs in CI and is green")
        # is unreachable.
        # 32 -> 33 adjudicated here, in the [F2.3] seeded CI project commit
        # (rulings 127, 187): ruling 187 item 3 orders a separate CI job for the
        # seeded golden project so `Feature check (fake AI)` is not lengthened,
        # and WP0.6 requires the direct `needs:` + `check_job` edge on `ci-gate`.
        assert len(direct) <= 33, f"ci-gate has {len(direct)} direct needs — review"


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


class TestNegativeClaimsJobWired(_CiYml):
    """DOCS-NJT's own wiring, pinned from OUTSIDE the job it defends.

    The gate test (scripts/test_negative_tooling_claims.py) cannot self-pin: a
    job that is deleted runs nothing, so an assertion living inside it fails to
    fire on the exact edit it is meant to catch. This file is the assertion's
    only sound home — it runs in `collection-sanity`, which has no `needs:` and
    no path filter, so it executes on every non-draft PR (a ci.yml-only edit
    included) whatever else is deleted.

    Teeth, measured rather than asserted: deleting the job + its `needs:` entry
    + its check_job line leaves `test_ci_job_graph.py` GREEN (it reported "42
    jobs, gate reaches 38" on that mutant — a closed-world checker cannot see a
    whole-gate deletion, only a half-delete). These three assertions close
    exactly that gap.
    """

    JOB = "docs-negative-claims"
    SUITE = "scripts/test_negative_tooling_claims.py"
    # The published leg name — what a reviewer must type into the checks list.
    # GitHub publishes a leg under the job's `name:`, never its YAML key, so a
    # drift between the two strings below is the "I can't find the check" bug.
    LEG = "Negative Tooling Claims in Docs (DOCS-NJT)"

    def test_the_job_still_exists_and_runs_the_suite(self) -> None:
        job = self.jobs.get(self.JOB)
        assert job is not None, (
            f"{self.JOB} has vanished from ci.yml — the negative-claim gate is "
            "now running in no job at all (this pin lives in collection-sanity "
            "precisely so the deletion cannot be silent)"
        )
        argv = " ".join(str(step.get("run", "")) for step in job.get("steps", []) or [])
        assert self.SUITE in argv, f"{self.SUITE} no longer invoked by {self.JOB}"
        assert job.get("name") == self.LEG, (
            f"{self.JOB}'s leg name is {job.get('name')!r}, not {self.LEG!r} — "
            "docs and PR bodies tell reviewers to search for the leg name"
        )

    def test_ci_gate_needs_it_and_reads_its_result(self) -> None:
        # Both halves: a `needs:` edge alone is ORDERING, only a result read is
        # GATING (AUDIT §2.1).
        assert self.JOB in _needs_of(self.jobs["ci-gate"]), (
            f"ci-gate no longer needs {self.JOB} — a red in it cannot flip the required context"
        )
        gate_run = "\n".join(
            step.get("run", "") for step in self.jobs["ci-gate"]["steps"] if step.get("run")
        )
        assert f"needs.{self.JOB}.result" in gate_run, (
            f"ci-gate needs {self.JOB} but never reads its result"
        )

    def test_check_job_line_names_the_leg_the_job_publishes(self) -> None:
        gate_run = "\n".join(
            step.get("run", "") for step in self.jobs["ci-gate"]["steps"] if step.get("run")
        )
        line = next((ln for ln in gate_run.splitlines() if f"needs.{self.JOB}.result" in ln), "")
        assert f'"{self.LEG}"' in line, (
            f"ci-gate's check_job line for {self.JOB} does not print its "
            f"`name:` ({self.LEG!r}) — the aggregated report and the checks "
            f"list would disagree about what to look for:\n  {line.strip()}"
        )


class TestSeededFeatureCheckJobWired(_CiYml):
    """Ruling 187 item 3: the seeded golden project runs in its own CI job,
    wired into ci-gate via direct need + check_job line (WP0.6)."""

    JOB = "feature-check-seeded"
    LEG = "Feature check (seeded)"
    CMD = "scripts/feature-check.sh --fake --seeded"

    def test_the_job_exists_and_runs_seeded_feature_check(self) -> None:
        job = self.jobs.get(self.JOB)
        assert job is not None, f"{self.JOB} is missing from ci.yml"
        argv = " ".join(str(step.get("run", "")) for step in job.get("steps", []) or [])
        assert self.CMD in argv, f"{self.CMD!r} not invoked by {self.JOB}"
        assert job.get("name") == self.LEG

    def test_ci_gate_needs_it_and_reads_its_result(self) -> None:
        assert self.JOB in _needs_of(self.jobs["ci-gate"]), f"ci-gate does not need {self.JOB}"
        gate_run = "\n".join(
            step.get("run", "") for step in self.jobs["ci-gate"]["steps"] if step.get("run")
        )
        assert f"needs.{self.JOB}.result" in gate_run, (
            f"ci-gate needs {self.JOB} but never reads its result"
        )


class TestFanInReplacesTheFakeJob(_CiYml):
    """[r264] Build: the single fake job became 4 shard jobs + a fan-in. The gate's
    one fake-check edge is the FAN-IN (the package's fifth bullet: the gate requires
    the fan-in in place of the single job, and stays the one required check); the
    shards are reached THROUGH the fan-in, not as direct needs of the gate, and the
    fan-in carries a shard's red in its own run body (the WP0.6 edge) — the matrix
    aggregate read, failure when any shard failed or was cancelled.
    """

    SHARDS = "feature-check-shards"
    FAN_IN = "feature-check-fan-in"
    LEG = "Feature check (fake AI)"

    def test_the_shard_jobs_exist_and_run_the_sharded_fake_check(self) -> None:
        job = self.jobs.get(self.SHARDS)
        assert job is not None, f"{self.SHARDS} is missing from ci.yml"
        argv = " ".join(str(step.get("run", "")) for step in job.get("steps", []) or [])
        assert "--fake --shard" in argv, f"a --shard invocation is missing from {self.SHARDS}"
        assert job.get("name") == self.LEG, "the shard matrix carries the tier's name"
        matrix = (job.get("strategy") or {}).get("matrix") or {}
        assert len(matrix.get("pair") or []) == 4, "the picked shape is N=4"
        # The backend golden tests run ONCE, in one shard: the wrapper passes --shard
        # everywhere, and feature_check.py runs the backend leg only on shard 1
        # (pinned in backend/tests/unit/scripts/test_feature_check.py).

    def test_the_fan_in_exists_and_runs_the_witness(self) -> None:
        job = self.jobs.get(self.FAN_IN)
        assert job is not None, f"{self.FAN_IN} is missing from ci.yml"
        argv = " ".join(str(step.get("run", "")) for step in job.get("steps", []) or [])
        assert "scripts.uplevel.inventory_witness" in argv, f"{self.FAN_IN} runs no witness"
        # the fan-in runs the witness ONCE: the shards carry no witness step
        shard_argv = " ".join(
            str(step.get("run", "")) for step in self.jobs[self.SHARDS].get("steps", []) or []
        )
        assert "inventory_witness" not in shard_argv, (
            "a shard runs the witness over a partial leg set"
        )

    def test_ci_gate_needs_the_fan_in_not_the_shards(self) -> None:
        needs = _needs_of(self.jobs["ci-gate"])
        assert self.FAN_IN in needs, f"ci-gate does not need {self.FAN_IN}"
        assert self.SHARDS not in needs, (
            "the shards are reached through the fan-in, not as gate needs"
        )
        assert "feature-check" not in needs, "the single fake job's need must be gone"
        gate_run = "\n".join(
            step.get("run", "") for step in self.jobs["ci-gate"]["steps"] if step.get("run")
        )
        assert f"needs.{self.FAN_IN}.result" in gate_run
        assert f"needs.{self.SHARDS}.result" not in gate_run, (
            "the gate reads the fan-in, not each shard — the aggregate is the fan-in's"
        )

    def test_the_fan_in_carries_a_shards_red_in_its_run_body(self) -> None:
        fan_script = "\n".join(
            step.get("run", "") for step in self.jobs[self.FAN_IN]["steps"] if step.get("run")
        )
        assert f"needs.{self.SHARDS}.result" in fan_script, (
            "the fan-in must read the shards' aggregate result itself — the edge that "
            "carries a failed/cancelled shard to a red fan-in (and the WP0.6 walker's edge)"
        )

    def test_the_merge_step_fails_on_every_bad_union_shape(self) -> None:
        # The merge step's fail conditions, as string-presence pins on its run
        # body (the same shape every other CI run-body pin here uses): the red
        # shard path has its own test below (it is also the walker's edge), and
        # these are the exits the [r264] package names — a shard label outside
        # 1/4..4/4, a duplicate shard, one leg running on two shards (any
        # outcome), a leg of the union that is not in the reference set, a
        # reference leg missing from the union (owner answer 6266229360, Q2:
        # set equality both ways in code). A missing shard summary is covered
        # by the same "no summary.json" literal as the label check's failure
        # mode, so it pins by consequence.
        fan_script = "\n".join(
            step.get("run", "") for step in self.jobs[self.FAN_IN]["steps"] if step.get("run")
        )
        assert "is not one of" in fan_script, (
            "the merge step no longer rejects a shard label outside 1/4..4/4"
        )
        assert "appears twice" in fan_script, "the merge step no longer rejects a duplicate shard"
        assert "ran on two shards" in fan_script, (
            "the merge step no longer rejects a leg running on two shards "
            "(any outcome — the split must partition the suite)"
        )
        assert "not in the reference set" in fan_script, (
            "the merge step no longer rejects a leg the shards ran that the "
            "reference set does not name (set equality both ways)"
        )
        assert "missing from the shards' union" in fan_script, (
            "the merge step no longer fails on a reference leg missing from the union"
        )
        assert "no summary.json for shard(s)" in fan_script, (
            "the merge step no longer fails closed on a shard that uploaded nothing"
        )

    def test_the_shards_are_reachable_from_the_gate(self) -> None:
        # Reachability is the production walker's own graph, not just the needs:
        # closure: a run-body `needs.X.result` read is an edge, and the fan-in's
        # matrix-aggregate read is the shards' ONLY route to the gate. Reuse the
        # walker itself (importlib, not a copy — same doctrine as
        # check-mock-spec.py reusing autospec-sweep.py: gate and sweep can never
        # disagree about what an edge is).
        import importlib.util

        _spec = importlib.util.spec_from_file_location(
            "test_ci_job_graph_reuse",
            Path(__file__).resolve().parent / "test_ci_job_graph.py",
        )
        assert _spec and _spec.loader
        _walker = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_walker)
        result_checked_needs = _walker.result_checked_needs

        seen: set[str] = set()
        stack = ["ci-gate"]
        while stack:
            name = stack.pop()
            if name in seen or name not in self.jobs:
                continue
            seen.add(name)
            job = self.jobs[name]
            stack += _needs_of(job)
            stack += sorted(result_checked_needs(job))
        assert self.FAN_IN in seen
        assert self.SHARDS in seen, (
            "the walker never reaches the shards: a red shard would be invisible"
        )

    def test_the_shard_setup_uv_tolerates_a_job_that_never_calls_uv(self) -> None:
        # [r264] backend-once left shards 2–4 with no uv invocation, and
        # setup-uv's post step (default ignore-nothing-to-cache: false) fails
        # "Cache path ... does not exist on disk" when nothing materialized the
        # cache dir — run 39209710736: three red jobs, every test leg green.
        # The pin is structural: the SHARD job's setup-uv carries the input.
        # Not a string pin on the run body (the action is `uses:`, not `run:`),
        # and deliberately scoped to this job: other setup-uv sites all invoke
        # uv in their own step list, so the default is correct there.
        setup_uv = [
            step
            for step in self.jobs[self.SHARDS]["steps"]
            if str(step.get("uses", "")).startswith("astral-sh/setup-uv@")
        ]
        assert len(setup_uv) == 1, "the shard job carries more than one setup-uv"
        assert setup_uv[0].get("with", {}).get("ignore-nothing-to-cache") is True, (
            "the shard job's setup-uv errors in its post step when the job "
            "never invokes uv (shards 2–4: nothing to cache)"
        )

    def test_the_reference_derivation_exports_an_absolute_scenario_path(self) -> None:
        # [r264] The Derive step runs --list from frontend/, and the specs read
        # FEATURE_CHECK_SCENARIOS with existsSync against their cwd: a
        # repo-relative value dies as frontend/backend/... and
        # event-detail-modal's module-scope constants crash collection past
        # their own test.skip guard (run 39209710736: the fan-in reddened on
        # "Cannot read properties of undefined (reading 'verdict')",
        # event-detail-modal.spec.ts:377). feature_check.py:2349 exports an
        # ABSOLUTE path to the real leg, so the derivation must mirror that
        # shape — pinned by consequence: the value must start at the
        # workspace, and the relative literal must be gone.
        env = next(
            step["env"]
            for step in self.jobs[self.FAN_IN]["steps"]
            if step.get("name") == "Derive the reference leg set (--list)"
        )
        scenarios = str(env["FEATURE_CHECK_SCENARIOS"])
        assert scenarios.startswith("${{ github.workspace }}"), (
            f"FEATURE_CHECK_SCENARIOS must be absolute, saw {scenarios!r} — the "
            "--list runs from frontend/ and the specs existSync against their cwd"
        )


class TestStepNamedSuitesStillWired(_CiYml):
    """The doc's "two sharpest absence-pins": wired by step invocation only.

    `docs/architecture/ai-pipeline-current-state.md` names these two suites and
    claimed their explicit CI wiring was pinned "by name" in this file. It
    wasn't — `git grep test_module_hygiene` returned ci.yml and prose only, so
    deleting ci.yml's hygiene run-line reddened nothing anywhere. This class is
    the assurance the doc promised, made true.

    They need a different pin from every other suite here. The five anti-rot
    gates above are pinned by SUITE PATH inside the battery's argv, which
    catches a re-wrap that drops a path. These two have mirror-image
    exposures:

      * `ai/tests/test_module_hygiene.py` is matched by the testpaths glob
        `ai/*/test_*.py` (measured: glob.glob returns 15 files, it is one; a
        bare `--collect-only` collects its 3 functions), so a path assertion
        proves nothing — deleting its step demotes a blocking probe to a
        unit-tier test with every leg green. Its exposure is the STEP
        disappearing, so the step NAME is the invariant.
      * `scripts/test_ai_surface_census.py` is the reverse: the glob cannot
        reach a `scripts/` path, the argv is the only thing that makes it run.
        test_antrot_step_names_all_gate_suites already lists it; restated here
        as a STEP-scoped assertion so a path relocated to another step of the
        same job still reddens, and so both members of the pair the doc names
        are covered by one class.

    Teeth, measured on scratch copies (never this tree), 13 passed unchanged:
    dropping ci.yml's hygiene run-line reddens 1 test
    (test_hygiene_step_still_runs_the_probes); renaming the step reddens 2 —
    the name is the shared handle, so _step() fails for both, which is the
    honest statement (my first draft of this docstring promised the rename
    reddened only the name test, and the mutant said otherwise); deleting the
    census path reddens 1 (test_census_still_named_in_the_antirot_step).
    """

    HYGIENE_PATH = "ai/tests/test_module_hygiene.py"
    HYGIENE_STEP = "Module hygiene probes"
    CENSUS_PATH = "scripts/test_ai_surface_census.py"
    ANTIROT_STEP = "Run the anti-rot gates' own tests"

    def _step(self, job: str, prefix: str) -> dict:
        for step in self.jobs[job].get("steps", []) or []:
            if str(step.get("name", "")).startswith(prefix):
                return step
        raise AssertionError(
            f"{job!r} has no step whose name starts {prefix!r} — the suite this "
            f"class defends is now invoked by nothing that can be found by name"
        )

    def test_hygiene_step_still_runs_the_probes(self) -> None:
        step = self._step("ai-tests", self.HYGIENE_STEP)
        assert self.HYGIENE_PATH in step.get("run", ""), (
            f"{self.HYGIENE_PATH} is no longer invoked by ai-tests' "
            f"{self.HYGIENE_STEP!r} step. A bare `uv run pytest` DOES still "
            "collect it (testpaths glob ai/*/test_*.py), so this suite can be "
            "silently demoted from a blocking probe to a unit-tier test and "
            "every leg stays green."
        )

    def test_hygiene_step_keeps_its_name(self) -> None:
        # The step name is the only addressable handle on this suite's CI
        # presence — the path proves nothing (see class docstring) — so the
        # name is what a re-wrap can quietly change.
        step = self._step("ai-tests", self.HYGIENE_STEP)
        assert step.get("name") == (
            "Module hygiene probes (import-time poisoning + triton shadow)"
        ), f"ai-tests hygiene step renamed: {step.get('name')!r}"

    def test_census_still_named_in_the_antirot_step(self) -> None:
        # Asserted on the STEP's run, not the job's concatenation: the path
        # could survive a re-wrap by landing in any other step of the same job,
        # which is a different exposure than the one the doc names.
        step = self._step("collection-sanity", self.ANTIROT_STEP)
        assert self.CENSUS_PATH in step.get("run", ""), (
            f"{self.CENSUS_PATH} dropped from collection-sanity's "
            f"{self.ANTIROT_STEP!r} step — it matches no testpaths entry, so "
            "outside that argv it runs nowhere."
        )
