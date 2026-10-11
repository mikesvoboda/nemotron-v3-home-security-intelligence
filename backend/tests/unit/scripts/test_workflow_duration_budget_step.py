"""The real-sleep budget gate is wired into CI (owner rulings 74 + 93).

""Done when: **the script is in the gate**"" — which is the one limb of the
ruling that a code review of ``scripts/`` cannot check. Pinned against the
workflow text rather than trusted, for a reason specific to this repo: the
``ci.yml`` footprint here is deliberately ONE added step inside the existing
``test-performance-audit`` job (hot-file discipline — a sibling lane rewrites
``ci.yml`` wholesale), and a one-hunk addition to a file another branch owns is
exactly the thing a merge quietly drops. If the step disappears, the script
keeps passing every one of its own tests and gates nothing.

Step placement is the ruling's own words: it "runs after the unit shards, like
the Test Performance Audit". The audit job already depends on the unit shards
and downloads their junit, so "after the shards" means "in this job, after its
analysis step" — asserted as an ordering, not a presence, because a step that
ran BEFORE the audit's analysis would read the same corpus and say nothing the
audit did not already say.

The budget envs are asserted because they are the only place the owner's
numbers are written for CI. Under ruling 93 those numbers are the audit's own
CI-set limits (unit 4.0 / integration 10.0 / e2e 10.0 — the exact values the
audit's "Analyze test durations" step sets as ``UNIT_TEST_THRESHOLD`` et al.)
plus the 1.5 s WARN; what the gate adds over the audit is the downgrade's
absence, not a stricter line. ``SLEEP_GATE_SLOW_BUDGET`` is deliberately NOT
set here: the tracked-slow 60 s cap is the script's default, identical to the
audit's ``SLOW_TEST_THRESHOLD: '60.0'`` two steps above, so a second copy in
this step's env would be a second place to keep in sync.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"
STEP_NAME = "Real-sleep budget gate (ruling 93)"
SCRIPT = "scripts/check-test-duration-budget.py"


def _audit_job_steps() -> list[dict]:
    """The parsed steps of the ``test-performance-audit`` job."""
    wf = yaml.safe_load(CI.read_text(encoding="utf-8"))
    job = wf["jobs"]["test-performance-audit"]
    return job["steps"]


def _step(name: str) -> dict:
    for step in _audit_job_steps():
        if step.get("name") == name:
            return step
    raise AssertionError(f"no step named {name!r} in test-performance-audit")


def _corpus_dir() -> str:
    """The results dir the audit's own download step fills.

    Read from the workflow rather than hard-coded: the gate has to point at
    whatever the downloads actually produce, and the downloads (not my memory)
    decide that.
    """
    for step in _audit_job_steps():
        with_ = step.get("with") or {}
        if step.get("uses", "").startswith("actions/download-artifact") and with_.get("path"):
            return str(with_["path"])
    raise AssertionError("no download-artifact step with a path in test-performance-audit")


def test_the_gate_step_exists_and_names_the_script() -> None:
    step = _step(STEP_NAME)
    assert SCRIPT in step["run"], (
        f"{STEP_NAME!r} must run {SCRIPT}, not something else with a similar name"
    )


def test_the_gate_reads_the_corpus_the_audit_downloads() -> None:
    """Same corpus, same tier classifier — the gate cannot see a different tree.

    If the gate pointed at a dir of its own it would be a second, narrower
    measurement, and the "durations CI already records" clause would be false.

    Equality on the argv token, not substring containment: the corpus dir is a
    PREFIX of the narrowed shapes this pin must kill — pointing the step at
    ``test-results/unit-only/`` (one shard instead of the merged corpus) keeps
    the substring "test-results" present while measuring a third of what CI
    recorded, which is exactly the "narrower measurement" the docstring bans.
    """
    corpus = _corpus_dir()
    tokens = _step(STEP_NAME)["run"].split()
    argv = tokens[tokens.index(SCRIPT) + 1 :]
    assert argv and argv[0].rstrip("/") == corpus.rstrip("/"), (
        "the gate's corpus argument must be EXACTLY the downloaded corpus dir "
        f"({corpus}), got {_step(STEP_NAME)['run']}"
    )


def test_the_gate_runs_after_the_audit_analysis() -> None:
    """ "After the unit shards, like the Test Performance Audit" — as an ordering.

    The audit's analysis step is what proves the shards' junit is on disk here;
    running before it would read the same files but claim nothing the audit had
    not already claimed, and running in a different job would need its own
    download step (which this footprint deliberately avoids).
    """
    names = [s.get("name") for s in _audit_job_steps()]
    assert "Analyze test durations" in names, "the audit's analysis step moved or renamed"
    assert STEP_NAME in names
    assert names.index("Analyze test durations") < names.index(STEP_NAME), (
        "the gate must follow the analysis step: post-run, like the audit"
    )


def test_the_gate_states_its_budgets_in_ci() -> None:
    """The owner's numbers, written once, in the workflow.

    Values asserted rather than mere presence. Under ruling 93 the hard
    budgets EQUAL the audit's CI-set limits and the WARN is 1.5 s; a step that
    set them to anything else (the old 1.5/6.0/5.0, or nothing at all) would
    look wired while gating a different rule than the one the owner ruled.
    """
    env = _step(STEP_NAME).get("env") or {}
    assert env == {
        "SLEEP_GATE_UNIT_BUDGET": "4.0",
        "SLEEP_GATE_INTEGRATION_BUDGET": "10.0",
        "SLEEP_GATE_E2E_BUDGET": "10.0",
        "SLEEP_GATE_WARN_BUDGET": "1.5",
    }, f"budgets are the ruling-93 record; got {env}"


def test_the_gate_is_the_only_added_step_in_the_audit_job() -> None:
    """Hot-file discipline, pinned.

    The ruling's CI footprint is one step riding the existing job — no new job,
    no new download, no second artifact reader — so that a sibling lane's
    wholesale ``ci.yml`` rewrite has exactly one hunk to reconcile. A future
    "just add a job" expansion silently breaks that agreement; this test makes
    it a conversation instead.
    """
    names = [s.get("name") for s in _audit_job_steps()]
    assert names.count(STEP_NAME) == 1
    # one step, and it is the only one whose run touches this script
    runs = [s.get("run", "") for s in _audit_job_steps()]
    assert sum(SCRIPT in str(r) for r in runs) == 1, (
        "the gate is one step; a second invocation is a second gate to keep in sync"
    )


def test_the_gate_step_has_no_baseline_fetch_behind_it() -> None:
    """Ruling 93's "no 'healthy in the previous main run' downgrade" at CI level.

    The audit's downgrade is powered by the "Fetch baseline junit" step feeding
    it a ``--baseline-dir``. This gate must have no equivalent — and after
    ruling 93 the ban is wider than ruling 74's: the script has NO baseline
    flag of any kind, so the step may not carry a previous-run DIRECTORY
    (``--baseline-dir``, ``--previous``, ``--ref``) OR the exemption FILE flag
    (``--baseline``) that ruling 74 allowed. The whole channel is gone, and a
    step that grew any part of it back would downgrade breaches in a job whose
    whole purpose is refusing to.
    """
    run = _step(STEP_NAME)["run"]
    assert not re.search(r"--baseline|--previous|--ref\b|--against", run), (
        f"a previous-run or exemption flag on the gate step reinstalls the downgrade: {run}"
    )
