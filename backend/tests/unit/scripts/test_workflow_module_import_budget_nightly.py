"""The [r172] module import budget nightly is wired (ruling 172, issue #7102).

""Done when: **the module budget fails CI on a reproduced import breach, the
warning-only nightly's list is posted**" — the second limb is a schedule's
property, which a code review of the script cannot check. The warning-only
pass on every PR ([r172]'s own clause) lives in ``ci.yml`` and is pinned by
``test_workflow_duration_budget_step.py``; THIS pin is the nightly: a separate
workflow file whose cron is the "scheduled nightly" the package names, running
the gate with ``SLEEP_GATE_MODULE_FAIL`` set so the verdict is real.

The file is separate from ``ci.yml`` for the same reasons the other nightlies
are (bundle-size, api-contract, api-compatibility — owner ruling 100 staggers
each off its own cron minute): a nightly red is triage-class, not
merge-blocking, and the WP0.6 invariant (``scripts/test_ci_job_graph.py``) is
a ``ci.yml`` invariant — a job that only runs on schedule would fail its
"reachable from ci-gate" check there, so the nightly's home is its own file.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
WF = REPO_ROOT / ".github" / "workflows" / "module-import-budget.yml"
SCRIPT = "scripts/check-test-duration-budget.py"
JOB = "module-import-budget"


def _wf() -> dict:
    return yaml.safe_load(WF.read_text(encoding="utf-8"))


def _job() -> dict:
    return _wf()["jobs"][JOB]


def test_the_nightly_exists_on_a_schedule() -> None:
    """ "After one scheduled nightly the modules over each threshold are posted."

    A manual-dispatch-only workflow is a nightly that never happens, and a
    cron-less file is a list nobody posts. The schedule leg is what makes
    the posting a fact of the calendar rather than a promise.
    """
    wf = _wf()
    triggers = wf[True] if True in wf else wf.get("on")  # PyYAML reads bare `on` as True
    assert triggers and "schedule" in triggers, (
        f"the nightly must run on a schedule, not dispatch alone: {list(triggers)}"
    )
    cron = triggers["schedule"][0]["cron"]
    assert cron == "31 3 * * *", f"the nightly's cron is UTC 03:31: {cron}"
    assert "workflow_dispatch" in triggers, "keep the on-demand run for debugging"


def test_the_cron_is_off_the_herd_and_distinct() -> None:
    """Ruling 100 staggers nightlies off the :00 herd, off each other.

    Pinned against the OTHER workflow files rather than from memory: the
    distinctness claim ("03:31 is not someone else's slot") is only true if
    read from every schedule in the tree, and a new sibling nightly that
    took 03:31 must fail here — two setup bursts colliding is exactly what
    the stagger is for.
    """
    other_crons: set[str] = set()
    for path in (REPO_ROOT / ".github" / "workflows").glob("*.yml"):
        if path.name == WF.name:
            continue
        try:
            wf = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        triggers = wf.get(True) if wf and True in wf else (wf.get("on") if wf else None)
        if not triggers:
            continue
        for entry in triggers.get("schedule") or []:
            if isinstance(entry, dict) and entry.get("cron"):
                other_crons.add(str(entry["cron"]))
    assert "31 3 * * *" not in other_crons, "03:31 is taken by another nightly"
    minute = int(WF and _wf()[True]["schedule"][0]["cron"].split()[0])
    assert minute % 10 != 0, "off the :00 herd (owner ruling 100)"


def test_the_nightly_runs_the_gate_in_failing_mode() -> None:
    """SLEEP_GATE_MODULE_FAIL=1 — this file is where the knob is ON.

    ci.yml's gate runs warning-only ([r172] ships that way); the nightly is
    the scheduled run where a reproduced import breach reddens. The knob is
    asserted on the step's env because an env key dropped by a merge is
    indistinguishable from the fail mode working — the same shape the
    ci.yml pin calls "the one way the amendment could vanish quietly".
    """
    steps = _job()["steps"]
    gate = [s for s in steps if SCRIPT in str(s.get("run", ""))]
    assert len(gate) == 1, f"the gate is one step: {[s.get('name') for s in steps]}"
    env = gate[0].get("env") or {}
    assert env.get("SLEEP_GATE_MODULE_FAIL") == "1", f"the nightly runs the FAILING mode; got {env}"
    assert env.get("SLEEP_GATE_MODULE_BUDGET") == "4.0", "UR-125's unit number, per module"
    assert env.get("SLEEP_GATE_MODULE_WARN") == "1.5", "UR-125's warn number, per module"
    assert env.get("SLEEP_GATE_RERUN") == "1", (
        "the module verdict needs a reproduced breach: UR-125's single re-run"
    )
    per_test = {k: v for k, v in env.items() if k.endswith("_BUDGET")}
    assert per_test == {
        "SLEEP_GATE_UNIT_BUDGET": "4.0",
        "SLEEP_GATE_INTEGRATION_BUDGET": "10.0",
        "SLEEP_GATE_E2E_BUDGET": "10.0",
        "SLEEP_GATE_WARN_BUDGET": "1.5",
        "SLEEP_GATE_MODULE_BUDGET": "4.0",
    }, f"the ruling-93 numbers ride unchanged with the module knobs: {per_test}"


def test_the_nightly_installs_the_dev_extra() -> None:
    """The module re-run's default runner is ``python -m pytest``.

    Same dependency the ci.yml gate's step pin asserts: without the dev
    extra's pytest the re-run cannot start, every module breach reports
    "pytest exit 4"-shaped unverified, and the nightly reddens on nothing
    while looking like it measured something.
    """
    installs = [s for s in _job()["steps"] if "uv sync" in str(s.get("run", ""))]
    assert installs and all("--extra dev" in str(s["run"]) for s in installs), (
        f"the dev extra is what puts pytest where the re-run needs it: {installs}"
    )


def test_the_nightly_runs_the_full_unit_corpus_in_one_job() -> None:
    """Per-suite import cost needs the suite's collection cost in ONE file.

    xdist across JOBS splits a module's collection cost across four junit
    writers; a corpus list that reads a shard sees a fraction of a stall.
    Within the job xdist stays on (as ci.yml's shards run it) — the re-run,
    which clears addopts, is where a single module's cost is measured
    exactly. The pytest target is the whole unit dir, not a subset: a
    narrower corpus would be a narrower measurement.
    """
    steps = _job()["steps"]
    pytest_step = next(
        s
        for s in steps
        if "--junit-xml" in str(s.get("run", "")) and "pytest" in str(s.get("run", ""))
    )
    run = str(pytest_step["run"])
    assert "backend/tests/unit/" in run, f"the full unit corpus, not a shard: {run}"
    assert "-n auto" in run and "--dist=worksteal" in run, (
        "same distribution flags as ci.yml's shards — the corpus this measures "
        "is the corpus the shards measure"
    )


def test_the_nightly_is_fail_closed() -> None:
    """No `|| true`, no `continue-on-error`, no masked verdict.

    The nightly's whole point is that a reproduced breach reddens a real
    run; a swallow here would make the failing mode decorative and the
    "posted list" the only evidence — which is the warning-only shape the
    knob is supposed to have left.
    """
    job = _job()
    assert not job.get("continue-on-error"), "the job must not swallow its verdict"
    for step in job["steps"]:
        run = str(step.get("run", ""))
        assert "|| true" not in run, f"a swallowed step: {step.get('name')}"
        assert not step.get("continue-on-error"), f"a swallowed step: {step.get('name')}"


def test_the_nightly_summary_carries_the_posted_list() -> None:
    """The "posted" limb: the gate's module rows reach the run's Summary tab.

    The gate script writes $GITHUB_STEP_SUMMARY itself (write_step_summary,
    the same channel ruling 93's WARN list uses), so the nightly needs no
    second reporting step re-reading a file — but the summary channel is
    load-bearing here, so the gate step's env must not be stripped of the
    runner-provided default. Pinned as: the gate step exists, and the
    workflow does not route $GITHUB_STEP_SUMMARY away from the gate's
    write (no override of that env anywhere in the job).
    """
    for step in _job()["steps"]:
        env = step.get("env") or {}
        assert "GITHUB_STEP_SUMMARY" not in env, (
            f"{step.get('name')} must not redirect the summary the gate writes to"
        )


def test_the_gate_reads_the_corpus_the_nightly_writes() -> None:
    """Path agreement between the corpus step and the gate step.

    The gate takes a results DIRECTORY and globs ``**/*.xml`` under it
    (``is_dir`` fails closed on a file path), so the nightly's pytest step
    must write its junit INTO the directory the gate step passes. The
    first cut wrote ``--junit-xml=test-results-unit-nightly.xml`` at the
    repo root and passed the gate ``test-results/`` — nothing populated
    that directory, so the gate failed closed ("results directory not
    found") every night from its first run, on wiring rather than on any
    module breach. No pin asserted the two paths agree, which is why the
    hole survived review. This pin is the agreement: the same directory
    literal appears on both sides, and the corpus step creates it.
    """
    steps = _job()["steps"]
    pytest_step = next(
        s
        for s in steps
        if "--junit-xml" in str(s.get("run", "")) and "pytest" in str(s.get("run", ""))
    )
    gate_step = next(s for s in steps if "check-test-duration-budget.py" in str(s.get("run", "")))
    m = re.search(r"--junit-xml=(\S+)", str(pytest_step["run"]))
    assert m, f"the corpus step writes no junit: {pytest_step['run']}"
    junit_path = m.group(1)
    gate_arg = str(gate_step["run"]).split()[-1].strip().rstrip("/")
    junit_dir = str(Path(junit_path).parent)
    assert junit_dir and gate_arg == junit_dir, (
        f"the gate must read the directory the corpus writes into: "
        f"junit {junit_path} vs gate arg {gate_arg!r}"
    )
    assert junit_path.endswith(".xml"), f"a junit file, not a directory: {junit_path}"
    assert f"mkdir -p {junit_dir}" in str(pytest_step["run"]), (
        f"the corpus step must create {junit_dir} before pytest writes into it"
    )


def test_an_xdist_mixed_corpus_row_is_named_not_posted_as_a_cost() -> None:
    """The nightly's corpus is xdist (-n auto), so its suite rows are mixed.

    pytest junit writes ONE <testsuite> for the whole xdist session: the
    suite ``time`` is wall-clock across workers, the testcase times are
    per-worker CPU-seconds, and ``suite - bodies`` across that pair is
    scheduler arithmetic, not an import cost (a real slice measured 14.14 s
    of bodies inside an 11.06 s suite — printed as -3.08 s before this
    check, and a garbage row posted nightly trains readers to ignore the
    list; a silently-dropped row trains them the same way). The corpus-side
    detector is the physical impossibility: CPU-seconds over wall-clock
    cannot happen in one process. This pin feeds that exact shape to
    ``suite_import_costs`` and asserts the suite lands on the unmeasured
    list with the reason named — never as a cost row, and never absent.
    """
    import importlib.util
    import xml.etree.ElementTree as ET

    script = REPO_ROOT / "scripts" / "check-test-duration-budget.py"
    spec = importlib.util.spec_from_file_location("_r172_gate_for_xdist", script)
    assert spec is not None and spec.loader is not None
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    suite_import_costs = gate.suite_import_costs

    with tempfile.TemporaryDirectory() as d:
        results = Path(d) / "results"
        results.mkdir()
        root = ET.Element("testsuites", name="pytest tests")
        suite = ET.SubElement(
            root,
            "testsuite",
            name="pytest",
            errors="0",
            failures="0",
            skipped="0",
            tests="2",
            time="11.060",
        )
        ET.SubElement(
            suite,
            "testcase",
            classname="backend.tests.unit.a.test_one",
            name="test_a",
            time="0.353",
        )
        ET.SubElement(
            suite,
            "testcase",
            classname="backend.tests.unit.b.test_two",
            name="test_b",
            time="13.787",
        )
        ET.ElementTree(root).write(results / "nightly-unit.xml")
        costs, unmeasured = suite_import_costs(results)
    assert not costs, f"the mixed suite must not read as a cost row: {costs}"
    assert len(unmeasured) == 1, f"the row must be named exactly once: {unmeasured}"
    (row,) = unmeasured
    assert "nightly-unit.xml / pytest" in row, f"named by its file and suite: {row}"
    assert "exceed" in row, f"the reason carries the physical-impossibility wording: {row}"
    assert "14.14" in row and "11.06" in row, f"both sides of the arithmetic in the row: {row}"
