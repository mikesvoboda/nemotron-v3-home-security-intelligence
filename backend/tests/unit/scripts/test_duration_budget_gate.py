"""Tests for scripts/check-test-duration-budget.py (owner rulings 74 + 93).

**The rule (ruling 93, 2026-10-11, amending ruling 74).** Verbatim: "Hard
fail: any unit test over **4.0 s**, with **no** 'healthy in the previous main
run' downgrade. That missing downgrade is what this gate adds over the Test
Performance Audit. Warn: any unit test over **1.5 s** is listed in the job
summary; it never fails the run. **No baseline file.**"

Three properties the Test Performance Audit deliberately does NOT have, and
which are the whole point of this gate — so they are pinned here rather than
assumed:

1. **No previous-run downgrade.** The audit's WP1.3 ``--baseline-dir`` machinery
   turns a mild breach on a baseline-healthy test into a warning. This gate may
   not: it reads no previous run and no exemption file of any kind.
   ``test_the_script_has_no_previous_run_machinery`` pins that structurally
   (argparse + AST + forbidden tokens) instead of trusting absence-of-behavior,
   because the audit is 500 lines of exactly that machinery one import away.
2. **No exemption channel at all.** Ruling 93 retired ruling 74's shrink-only
   baseline: the gate has no ``--baseline``, no ``--update``, and ships no
   baseline file. A committed 51-id file could not cover a victim set that
   rotates (over the three shipping green-main corpora: 31/22/17 ids over
   1.5 s, intersection 10 — re-measured by self-review F6); with
   nothing to hold today's slow tests, the only sane hard line is the audit's
   own limit, where the measured corpus flips zero ids.
3. **Fail closed on zero evidence.** A missing or empty results dir is a
   pipeline break, not a pass — the audit's own WP0.5 reasoning, "no more
   'skip + exit 0' on missing data … zero XML is a pipeline break -> fail".
   That rule reaches one level deeper than file *count*: XML files that carry
   no usable duration at all (truncated upload, writer killed mid-flush) are
   the same broken-upload shape.

The WARN tier is ruling 93's new half and gets its own pins: unit tests over
1.5 s are listed (stdout + ``$GITHUB_STEP_SUMMARY`` when set) and never fail
the run — including in the shapes that could make a WARN tier harmful: a
warned test must not also print as a breach, a failing run must still populate
the summary, and an unwritable summary path must not change the verdict.

Tier classification is NOT reimplemented in either file: the gate calls the
audit's ``categorize_test``, so the two can never disagree about what tier a
test is. (The classifier's number is the one that re-measures: 46 unit ids over
1.5 s in the three shipping corpora, because it routes the
299-collected-test ``test_gpu_monitor_batch28_*`` cluster to ``integration`` on
its "gpu" substring and the five over-1.5 s tracked-slow members to ``slow``.
This lane's first path-guessing pass over-counted; self-review F4 showed a
naive guesser's total depends on its own heuristic — two re-implementations
produced two different totals from the same corpora — so the classifier-side
number is the only one cited here.)

**Fixture-path hazard, and why the corpus dir is named ``corpus``.**
``categorize_test`` classifies from the whole file path, and pytest's
``tmp_path`` embeds the *test function's own name*. A test named
``test_integration_…`` therefore classifies every fixture it writes as
integration no matter what the fixture says. The tier-sensitive tests below are
named accordingly (integration-named tests assert integration, unit-named tests
avoid the substrings "e2e", "integration", "contract", "chaos", "gpu",
"security"), and the e2e cases carry the tier in the *filename* the way
Playwright does. ``corpus`` is tier-neutral by construction.

**The Done-when cases are replayed at the durations the record holds** (ruling
93's own words: "the redis backoff at ~4.7 s as a unit test; the banner spec at
~23 s against the e2e 10.0 s limit"). The redis case's recorded durations are
3.85 s (commit ``99394f95d``), 4.11 s and 4.31 s on main, 4.68 s locally — the
over-4.0 trio is replayed RED, and the 3.85 s commit-recorded sample is
replayed separately as WARN-not-fail: under a 4.0 s hard budget that sample
lands in the warn band, and saying so is the honest shape of "would have
failed it" (the number the corpus actually reddened on was 4.11/4.31, not
3.85). The banner spec's 23.1 s (commit ``3cdce4e3f``) is replayed against the
10.0 s e2e limit, and both cases' FIXED durations are replayed GREEN.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import re
import subprocess
import sys
import textwrap
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPO_ROOT / "scripts" / "check-test-duration-budget.py"
BASELINE_FILE = REPO_ROOT / "scripts" / "duration-budget-baseline.json"

# The gate's OWN classifier, loaded the way the gate loads the audit's: by
# path, offline. The M8 pin below asks the real categorize_test whether a
# fixture id is outside the tracked set instead of assuming it — an
# assumption there was exactly how the first M8 probe "passed" for the
# wrong reason (the id classified as integration, so the fallback never ran).
_spec = importlib.util.spec_from_file_location("_r93_gate_under_test", SCRIPT)
assert _spec is not None and _spec.loader is not None
_gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_gate)
categorize_test = _gate.categorize_test
# Read, never restated: a pin that hardcodes 5 passes when someone raises the
# bound in the script and the pins quietly stop describing the rule. The cap
# pin below asserts the SHAPE of the cap (per tier) against this value.
MAX_RERUNS = _gate.MAX_RERUNS
KNOWN_TIERS = frozenset({"unit", "integration", "e2e", "slow", "benchmark"})

# Same knob set the script reads; the CI step sets the same five values
# (ruling 93: the audit's CI-set limits + the 1.5 s WARN).
BUDGETS = {
    "SLEEP_GATE_UNIT_BUDGET": "4.0",
    "SLEEP_GATE_INTEGRATION_BUDGET": "10.0",
    "SLEEP_GATE_E2E_BUDGET": "10.0",
    "SLEEP_GATE_SLOW_BUDGET": "60.0",
    "SLEEP_GATE_WARN_BUDGET": "1.5",
}

REDIS_CASE = (
    "backend.tests.unit.core.test_redis",
    "test_get_redis_optional_returns_none_on_connection_error",
)
BANNER_CASE = (
    "specs/verdict-engine-banner.spec.ts",
    "verdict-engine banner (F1.2) > banner appears when the engine goes down and clears when it recovers",
)
# The redis backoff's recorded durations that ARE over 4.0 s: 4.11 s and
# 4.31 s measured on main runs, 4.68 s locally (PR body "two 10-10 cases";
# ruling 93's "~4.7 s" is that local figure).
REDIS_OVER_4 = (4.11, 4.31, 4.68)


def _xml(testcases: list[tuple[str, str, float]]) -> str:
    """A junit file: one ``<testcase>`` per test, as pytest's reporter emits."""
    lines = ['<?xml version="1.0" encoding="utf-8"?>', '<testsuite name="s">']
    for classname, name, t in testcases:
        lines.append(f'  <testcase classname="{classname}" name="{name}" time="{t}"/>')
    lines.append("</testsuite>")
    return "\n".join(lines) + "\n"


def _results(tmp_path: Path, *files: tuple[str, str]) -> Path:
    """Write ``(filename, xml-text)`` pairs into a results dir.

    One level deep under a tier-neutral ``corpus/shard/`` dir, the way CI's
    ``merge-multiple`` artifact download nests them — so the recursive glob is
    exercised rather than assumed, and nothing about the tier comes from the
    directory name.
    """
    out = tmp_path / "corpus" / "shard"
    out.mkdir(parents=True, exist_ok=True)
    for filename, text in files:
        (out / filename).write_text(text, encoding="utf-8")
    return tmp_path / "corpus"


def _run(
    results_dir: Path,
    env_extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, **BUDGETS}
    # The repo's own suite runs inside GitHub Actions, where
    # GITHUB_STEP_SUMMARY is set — popping keeps test WARN rows out of the
    # real job summary; tests that exercise the summary path set it back.
    env.pop("GITHUB_STEP_SUMMARY", None)
    env.update(env_extra or {})
    return subprocess.run(  # noqa: S603  # intentional - tests our own script, offline
        [sys.executable, str(SCRIPT), str(results_dir)],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _out(run: subprocess.CompletedProcess[str]) -> str:
    return run.stdout + run.stderr


def _run_defaults(
    results_dir: Path,
    env_extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the script with EVERY ``SLEEP_GATE_*`` key stripped from the env.

    ``_run`` injects the full budget dict, so it always measures the gate
    against test-supplied numbers and never against the script's own
    ``DEFAULT_*`` constants. That is a coverage hole with teeth: the ``ci.yml``
    step deliberately leaves ``SLEEP_GATE_SLOW_BUDGET`` unset (its comment
    says the 60 s cap is the script default, one place to keep in sync), so in
    production the tracked-slow cap the whole interpretation argument rests on
    is ``DEFAULT_SLOW_BUDGET`` itself — and injecting it in a test proves
    nothing about that constant. This helper runs with none set, so the
    verdicts are produced by the module-level defaults and a drift of any one
    of them reddens a pin.
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("SLEEP_GATE_")}
    env.pop("GITHUB_STEP_SUMMARY", None)  # same isolation as _run
    env.update(env_extra or {})
    return subprocess.run(  # noqa: S603  # intentional - tests our own script, offline
        [sys.executable, str(SCRIPT), str(results_dir)],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


# --------------------------------------------------------------------------
# Ruling 93's Done-when pair: a test over 4.0 s fails, one under passes.
# --------------------------------------------------------------------------


def test_a_unit_test_over_four_seconds_fails_the_gate(tmp_path: Path) -> None:
    results = _results(
        tmp_path,
        ("unit.xml", _xml([("backend.tests.unit.slow.test_sleeper", "test_sleeps", 4.5)])),
    )
    run = _run(results)
    assert run.returncode != 0, (
        "a unit test at 4.5 s is over the 4.0 s hard budget; exit 0 here is "
        f"ruling 93 unimplemented\nstdout: {run.stdout}\nstderr: {run.stderr}"
    )
    assert "test_sleeps" in _out(run), "the breach must name the test"
    assert "4.0" in _out(run), "the message must state the budget it breached"


def test_a_unit_test_under_four_seconds_passes_the_gate(tmp_path: Path) -> None:
    results = _results(
        tmp_path,
        ("unit.xml", _xml([("backend.tests.unit.quick.test_fast", "test_fast", 0.2)])),
    )
    run = _run(results)
    assert run.returncode == 0, (
        "a unit test at 0.2 s is under budget; a gate that reddens ordinary "
        f"tests is noise the owner silences\nstdout: {run.stdout}\nstderr: {run.stderr}"
    )


def test_a_unit_test_in_the_warn_band_passes_and_is_warned(tmp_path: Path) -> None:
    """The ruling-93 discriminator, and the one the 1.5 s gate got wrong.

    2.0 s is over WARN (1.5) and under the hard budget (4.0): rc=0, and the
    id is LISTED (the "listed in the job summary" limb — stdout is the local
    rendering of it). Under the old 1.5 s hard budget this exact shape
    reddened innocent tests; the measured over-1.5 set rotated 31/22/17 ids
    (intersection 10) across the three shipping green-main corpora, which is
    what ruling 93 fixed.
    """
    results = _results(
        tmp_path,
        ("unit.xml", _xml([("backend.tests.unit.band.test_mid", "test_mid", 2.0)])),
    )
    run = _run(results)
    assert run.returncode == 0, (
        "2.0 s must WARN, not fail: 'any unit test over 1.5 s is listed in "
        f"the job summary; it never fails the run'\n{_out(run)}"
    )
    out = _out(run)
    assert "WARN" in out and "1.5" in out, f"the warn tier must be labelled\n{out}"
    assert "2.00s" in out and "test_mid" in out, f"the warn list must name and size it\n{out}"


# --------------------------------------------------------------------------
# The WARN tier's own contract: listed, summarized, harmless.
# --------------------------------------------------------------------------


def test_the_warn_list_lands_in_the_step_summary(tmp_path: Path) -> None:
    """ "listed in the job summary" is the destination, not a metaphor.

    ``$GITHUB_STEP_SUMMARY`` is where the owner reads the numbers; the WARN
    rows have to appear there, not only in a scrollback log.
    """
    summary = tmp_path / "step-summary.md"
    results = _results(
        tmp_path,
        (
            "unit.xml",
            _xml(
                [
                    ("backend.tests.unit.slowish.test_a", "test_a", 2.5),
                    ("backend.tests.unit.quick.test_b", "test_b", 0.1),
                ]
            ),
        ),
    )
    run = _run(results, {"GITHUB_STEP_SUMMARY": str(summary)})
    assert run.returncode == 0, f"2.5 s is WARN-only\n{_out(run)}"
    written = summary.read_text(encoding="utf-8")
    assert "backend.tests.unit.slowish.test_a::test_a" in written, (
        f"the summary must name the warned test\n{written}"
    )
    assert "backend.tests.unit.quick.test_b" not in written, (
        f"the summary must not list under-WARN tests\n{written}"
    )
    assert "1.5" in written, f"the summary must state the threshold\n{written}"


def test_the_warn_section_survives_a_failing_run(tmp_path: Path) -> None:
    """The summary must populate on RED runs too — the red run is exactly
    when the owner wants the distribution in front of them."""
    summary = tmp_path / "step-summary.md"
    results = _results(
        tmp_path,
        (
            "unit.xml",
            _xml(
                [
                    ("backend.tests.unit.slowish.test_a", "test_a", 4.5),
                    ("backend.tests.unit.band.test_b", "test_b", 2.0),
                ]
            ),
        ),
    )
    run = _run(results, {"GITHUB_STEP_SUMMARY": str(summary)})
    assert run.returncode != 0, "4.5 s is a breach"
    written = summary.read_text(encoding="utf-8")
    for tid in (
        "backend.tests.unit.slowish.test_a::test_a",
        "backend.tests.unit.band.test_b::test_b",
    ):
        assert tid in written, f"both over-1.5 ids belong in the summary: {tid}\n{written}"


def test_warn_alone_never_fails_the_run(tmp_path: Path) -> None:
    """A whole band of 1.5-4.0 s tests and still green: this IS today's
    corpus shape (46 unit ids over 1.5 s across three green main runs)."""
    results = _results(
        tmp_path,
        (
            "unit.xml",
            _xml(
                [
                    (f"backend.tests.unit.band.test_{i}", f"test_{i}", d)
                    for i, d in enumerate([1.6, 2.2, 2.8, 3.1, 3.5, 3.9])
                ]
            ),
        ),
    )
    run = _run(results)
    out = _out(run)
    assert run.returncode == 0, (
        "six WARN-band tests must not fail the run — at 1.5 s hard, this "
        f"corpus is exactly the rotation lottery ruling 93 killed\n{out}"
    )
    for i in range(6):
        assert f"test_{i}" in out, f"every warned id must be listed: test_{i}\n{out}"


def test_a_warn_band_test_is_not_reported_as_a_breach(tmp_path: Path) -> None:
    """Anti-conflation: WARN must not print BREACH. A report that lists the
    warn rows under the breach header makes the tier distinction a lie even
    though rc=0 is right."""
    results = _results(
        tmp_path,
        ("unit.xml", _xml([("backend.tests.unit.band.test_a", "test_a", 2.0)])),
    )
    run = _run(results)
    assert run.returncode == 0
    assert "BREACH" not in run.stdout, f"a WARN row must not appear as a breach\n{run.stdout}"
    assert run.stdout.strip().splitlines()[-1].startswith("RESULT: PASS"), run.stdout


def test_an_unwritable_step_summary_never_breaks_the_gate(tmp_path: Path) -> None:
    """The WARN tier exists to not-fail. A summary-write failure (odd
    permissions, a path that is a directory) must degrade to stderr, never
    flip the verdict or crash with a traceback."""
    results = _results(
        tmp_path,
        ("unit.xml", _xml([("backend.tests.unit.band.test_a", "test_a", 2.0)])),
    )
    run = _run(results, {"GITHUB_STEP_SUMMARY": str(tmp_path)})  # a DIRECTORY
    assert run.returncode == 0, f"an unwritable summary must not fail the run\n{_out(run)}"
    assert "Traceback" not in _out(run), f"must degrade, not crash\n{_out(run)}"
    assert "WARN" in _out(run), "the WARN list still goes to stdout\n" + _out(run)


# --------------------------------------------------------------------------
# No baseline file, no exemption flags — ruling 93's "No baseline file."
# Pinned structurally because the audit's machinery is one import away and
# a forgotten exemption flag is invisible to behavior tests.
# --------------------------------------------------------------------------


def test_no_baseline_file_ships() -> None:
    """The artifact-level pin: the file ruling 74 required is gone."""
    assert not BASELINE_FILE.exists(), (
        f"{BASELINE_FILE} must not exist — ruling 93: 'No baseline file.'"
    )


def _add_argument_params() -> set[str]:
    """Every parameter the script passes to ``add_argument``.

    Built from the calls, not from a substring scan of the file: a substring
    scan of the source would trip on the word "baseline" used in prose (the
    docstring explains what was retired) and would let a flag merely
    *lacking* the forbidden substring through.
    """
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    params: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "add_argument":
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        params.add(arg.value)
    return params


def test_the_script_has_no_previous_run_machinery() -> None:
    """Structural pin on "no downgrade, no baseline file", ruling 93 shape.

    Three arms. (a) The script's ONLY argparse parameter is the positional
    corpus — no --baseline, no --update, no previous-dir flag of any kind.
    (b) No glob in the source lacks a wildcard and no directory enumeration
    appears at all: the audit finds the previous run by enumerating the
    directory it was handed, so a script that only ever globs ``*.xml`` out
    of the results dir cannot be reading a second corpus. (c) Forbidden
    tokens: the audit's env name and the retired file's name may not appear,
    so the machinery cannot re-enter through env or a default path.
    """
    src = SCRIPT.read_text(encoding="utf-8")

    params = _add_argument_params()
    flags = {p for p in params if p.startswith("-")}
    offending = sorted(
        f
        for f in flags
        if "baseline" in f
        or "update" in f
        or "previous" in f
        or f in {"--ref", "--reference", "--against", "--exempt", "--allow"}
    )
    assert not offending, (
        f"ruling 93 retired the exemption machinery entirely; flags survive: {offending}"
    )
    assert params == {"results_dir"}, (
        f"the only CLI input is the positional corpus — no flag, no second positional: {params}"
    )

    tree = ast.parse(src)
    GLOBS = {"glob", "rglob"}
    ENUMERATORS = {"iterdir", "listdir", "scandir", "walk"}
    glob_targets: list[str] = []
    enumerated: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # attr access (path.glob) or bare name (os.walk / os.listdir)
        fname = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
        if fname in GLOBS:
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    glob_targets.append(arg.value)
        elif fname in ENUMERATORS:
            # The audit finds the previous run by enumerating a directory.
            # This script has exactly one corpus to scan, via one wildcard
            # glob of the results dir — any OTHER directory enumeration is
            # that channel, so it is banned outright rather than inspected.
            enumerated.append(fname)
    assert glob_targets and all("*" in g for g in glob_targets), (
        "a glob with no wildcard is scanning some corpus other than the results "
        f"dir: {glob_targets}"
    )
    assert not enumerated, (
        "iterdir/listdir/scandir/walk is how a second corpus gets read (a "
        f"wildcard glob was the only permitted scan): {enumerated}"
    )
    # BASELINE_DIR (upper-case) is the AUDIT's env name for its previous-run
    # directory. The retired file/env names are listed too: this gate must
    # not quietly grow back the channel ruling 93 deleted.
    for forbidden in (
        "baseline_dir",
        "BASELINE_DIR",
        "previous_run",
        "fetch-ci-artifacts",
        "duration-budget-baseline",
        "SLEEP_GATE_BASELINE",
        "SLEEP_GATE_UPDATE",
    ):
        assert forbidden not in src, f"{forbidden} is machinery ruling 93 removed"


def test_a_sibling_baseline_dir_is_not_read(tmp_path: Path) -> None:
    """The downgrade pinned BEHAVIORALLY, in the shape CI actually ships it.

    The audit's fetch step (ci.yml "Fetch baseline junit") writes the previous
    run's junit into ``baseline/`` — a SIBLING of ``test-results/``. So the
    honest test of "no previous-run downgrade" hands the gate that exact
    layout: a breaching corpus (4.5 s, over the hard budget) beside a baseline
    corpus in which the same test was healthy. The audit, given
    ``--baseline-dir``, downgrades that breach to a warning (WP1.3's mild-spike
    rule). This gate must stay RED — same fixture, opposite verdict, and the
    difference IS the ruling.

    A mutant that reads a sibling dir through any idiom the structural pin
    above happens to miss still dies here, because unlike the pin this fixture
    actually creates the directory.
    """
    results = _results(
        tmp_path,
        ("unit.xml", _xml([("backend.tests.unit.slow.test_sleeper", "test_a", 4.5)])),
    )
    prev = tmp_path / "baseline" / "shard"
    prev.mkdir(parents=True)
    (prev / "unit.xml").write_text(
        _xml([("backend.tests.unit.slow.test_sleeper", "test_a", 0.05)]),
        encoding="utf-8",
    )
    run = _run(results)
    assert run.returncode != 0, (
        "a healthy baseline/ sibling must buy nothing — this is precisely the "
        "'healthy in the previous run' downgrade the ruling forbids, and the "
        f"audit would have warned here\nstdout: {run.stdout}\nstderr: {run.stderr}"
    )


# --------------------------------------------------------------------------
# Fail closed on zero evidence.
# --------------------------------------------------------------------------


def test_xml_files_without_durations_fail_the_gate(tmp_path: Path) -> None:
    """Files present, durations absent → RED, not a vacuous PASS.

    ``xml_count`` counts FILES and is incremented before the parse, so a
    truncated upload (or a writer killed mid-flush) yields "N files, 0 tests
    with a recorded duration". Over-budget is then empty and the plain-PASS
    branch is one line away — the gate would certify a corpus it never read.
    The WP0.5 rule that covers an empty dir has to reach this shape too.
    """
    out = tmp_path / "corpus" / "shard"
    out.mkdir(parents=True)
    (out / "unit.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<testsuite name="s">'
        '<testcase classname="backend.tests.unit.trunc.test_a" name="test_a" time=""/>'
        '<testcase classname="backend.tests.unit.trunc.test_b" name="test_b"/>'
        '<testcase classname="backend.tests.unit.trunc.test_c" name="test_c" time="n/a"/>'
        "</testsuite>\n",
        encoding="utf-8",
    )
    run = _run(tmp_path / "corpus")
    assert run.returncode != 0, (
        "junit files with no usable durations must fail the gate: exit 0 here "
        "passes vacuously on unread data, the exact fail-open the zero-XML rule "
        f"exists to prevent\nstdout: {run.stdout}\nstderr: {run.stderr}"
    )
    assert "0 test(s) with a recorded duration" in _out(run), (
        "the message must say what was missing — files found, durations absent — "
        f"so it is diagnosable as corruption rather than an empty corpus: {_out(run)}"
    )


def test_zero_xml_fails_the_gate(tmp_path: Path) -> None:
    """No XML at all is a pipeline break, never a pass.

    Mirror of the audit's WP0.5 rule: "the audit only runs when its tier ran …
    so zero XML is a pipeline break -> fail". Not hypothetical here — both
    artifact downloads in this job carry ``continue-on-error: true``, so a
    broken upload looks exactly like an empty corpus and a gate that exits 0 on
    it is switched off silently.
    """
    results = tmp_path / "corpus"
    results.mkdir()
    run = _run(results)
    assert run.returncode != 0, f"zero XML must be RED\n{_out(run)}"


def test_a_missing_results_dir_fails_the_gate(tmp_path: Path) -> None:
    run = _run(tmp_path / "never-written")
    assert run.returncode != 0, f"a missing dir is the same vacuous-green risk\n{_out(run)}"


def test_skips_are_not_evidence_of_a_fast_test(tmp_path: Path) -> None:
    """``time="0"`` / no-``time`` is a SKIP, not a measured-fast pass.

    Both corpus shapes are real: pytest omits the ``time`` attribute on skipped
    testcases entirely (the script's ``case.get("time", "0")`` default is that
    arm) and Playwright's reporter emits ``time="0"`` for skipped specs — both
    verified in the three green main corpora. Dropping duration<=0 (the audit's
    convention) is load-bearing: an ALL-skipped corpus is "0 test(s) with a
    recorded duration", the corrupt-upload shape, RED. Record skips at 0.0
    instead and the same corpus becomes a healthy PASS.
    """
    skipped = (
        '  <testcase classname="backend.tests.unit.skips.test_a" name="test_one"><skipped/></testcase>'
        '  <testcase classname="backend.tests.unit.skips.test_b" name="test_two" time="0.0"/>'
    )
    all_skips = _results(
        tmp_path,
        (
            "unit.xml",
            f'<?xml version="1.0" encoding="utf-8"?><testsuite name="s">\n{skipped}\n</testsuite>\n',
        ),
    )
    run = _run(all_skips)
    assert run.returncode != 0, (
        "an all-skipped corpus recorded 0 durations — fail-closed, not a "
        f"vacuous pass on skipped tests\n{_out(run)}"
    )
    assert "0 test(s) with a recorded duration" in _out(run), (
        f"the message must name the zero-duration shape\n{_out(run)}"
    )


# --------------------------------------------------------------------------
# Ruling 93's Done-when pair, replayed at the recorded durations.
# --------------------------------------------------------------------------


def test_the_redis_backoff_case_would_have_failed_the_gate(tmp_path: Path) -> None:
    """Done-when case 1: real exponential backoff as a UNIT test, over 4.0 s.

    ``99394f95d`` zeroed ``RedisClient._calculate_backoff_delay`` for the two
    ``get_redis_optional`` failure tests; before it, ``connect()`` slept its
    real 1 s + 2 s + jitter across three attempts. The durations the record
    holds: 3.85 s (commit message), 4.11 s and 4.31 s on main, 4.68 s locally
    — ruling 93's "~4.7 s" is the local figure. Every recorded number over
    the 4.0 s hard budget is replayed here; each must be RED.
    """
    for duration in REDIS_OVER_4:
        results = _results(tmp_path, (f"unit-{duration}.xml", _xml([(*REDIS_CASE, duration)])))
        run = _run(results)
        assert run.returncode != 0, (
            f"the redis backoff at {duration} s is over the 4.0 s hard budget — "
            f"this is the named Done-when class\nstdout: {run.stdout}\nstderr: {run.stderr}"
        )
        assert REDIS_CASE[1] in _out(run), "the breach must name the redis test"


def test_the_commit_recorded_3_85s_redis_sample_warns_not_fails(tmp_path: Path) -> None:
    """The honest half of "would have failed it".

    3.85 s is the duration ``99394f95d`` itself records — UNDER ruling 93's
    4.0 s budget, so that sample WARNs rather than fails. The corpus numbers
    that actually reddened the audit were 4.11/4.31 s on main (pinned above).
    A pin that replayed 3.85 s as a breach would be asserting a falsehood
    about the calibration the owner chose: 4.0 is the line, and this test
    says exactly where 3.85 sits relative to it — loudly listed, never red.
    """
    results = _results(tmp_path, ("unit-shard.xml", _xml([(*REDIS_CASE, 3.85)])))
    run = _run(results)
    assert run.returncode == 0, (
        f"3.85 s is under the 4.0 s budget — WARN band, not a breach\n{_out(run)}"
    )
    out = _out(run)
    assert "WARN" in out and REDIS_CASE[1] in out, (
        f"the 3.85 s sample must still be listed loudly\n{out}"
    )
    assert "BREACH" not in run.stdout, f"warned is not breached\n{run.stdout}"


def test_the_fixed_redis_test_at_232ms_is_green(tmp_path: Path) -> None:
    """And the redis case today, at its real corpus duration, is green.

    0.232 s is the middle of what the three green main runs record (0.188 /
    0.232 / 0.282 — measured per-run, shard-3, same id) now that the backoff
    is patched away — the pair with the over-4.0 cases is the whole point of
    the gate: the fix moves a test from breach to well under any line.
    """
    results = _results(tmp_path, ("unit-shard.xml", _xml([(*REDIS_CASE, 0.232)])))
    run = _run(results)
    assert run.returncode == 0, (
        f"the fixed redis test is 0.23 s\nstdout: {run.stdout}\nstderr: {run.stderr}"
    )


def test_the_banner_case_would_have_failed_the_gate(tmp_path: Path) -> None:
    """Done-when case 2: 23.1 s of real readiness waiting in the banner spec,
    against the e2e 10.0 s limit — ruling 93 names the limit explicitly.

    ``3cdce4e3f`` replaced two real 15 s polls with a fake clock. The corpus
    file is Playwright's own junit reporter (``e2e-results.xml``), which the
    audit job downloads into the same ``test-results/`` dir, so
    ``categorize_test`` sees the e2e tier and the 10.0 s e2e budget applies —
    the interpretation recorded in the PR body: a strictly unit-scoped gate
    cannot make an e2e spec fail, and the ruling names this case.
    """
    results = _results(tmp_path, ("e2e-results.xml", _xml([(*BANNER_CASE, 23.1)])))
    run = _run(results)
    assert run.returncode != 0, (
        "23.1 s against a 10.0 s e2e limit is 2.3x over; this is the second "
        f"named Done-when case\nstdout: {run.stdout}\nstderr: {run.stderr}"
    )
    out = _out(run)
    assert "verdict-engine" in out, "the breach must name the banner spec"
    assert "10.0" in out, f"the message must state the e2e limit it breached\n{out}"


def test_the_fixed_banner_spec_at_2600ms_is_green(tmp_path: Path) -> None:
    """The same spec after the fix: 2.6 s, under the 10.0 s e2e limit.

    Measured, not invented — the current corpus's banner spec runs 1.58-2.60 s.
    Without this arm, a gate that reddens every e2e test would pass the case
    above for the wrong reason.
    """
    results = _results(
        tmp_path,
        ("e2e-results.xml", _xml([("specs/verdict-engine-banner.spec.ts", "banner clears", 2.6)])),
    )
    run = _run(results)
    assert run.returncode == 0, (
        "the fixed banner spec is the green half of the banner Done-when case"
        f"\nstdout: {run.stdout}\nstderr: {run.stderr}"
    )


# --------------------------------------------------------------------------
# Per-tier limits (the audit's own, without its downgrade).
# --------------------------------------------------------------------------


def test_orchestrator_under_its_tier_budget_is_green(tmp_path: Path) -> None:
    """5.5 s is legal for integration (limit 10.0), not for unit.

    Named for the measured max: the 3 green main runs top out at 5.44 s on
    ``test_orchestrator_integration::test_api_start_stopped_service``, so a
    5.5 s integration test is today's normal and the limit must clear it.
    """
    results = _results(
        tmp_path,
        ("integration.xml", _xml([("backend.tests.integration.test_orch", "test_start", 5.5)])),
    )
    run = _run(results)
    assert run.returncode == 0, f"integration's limit is 10.0 s, not the unit 4.0\n{_out(run)}"


def test_orchestrator_over_its_tier_budget_is_red(tmp_path: Path) -> None:
    results = _results(
        tmp_path,
        ("integration.xml", _xml([("backend.tests.integration.test_orch", "test_start", 10.5)])),
    )
    run = _run(results)
    assert run.returncode != 0, f"10.5 s is over the 10.0 s integration limit\n{_out(run)}"
    assert "10.0" in _out(run), "the message must state the limit breached"


def test_a_unit_breach_is_not_forgiven_by_a_looser_tier_budget(tmp_path: Path) -> None:
    """5.5 s is green for integration and red for unit: the tier is load-bearing.

    The classifier picks the tier, so a plain unit test cannot borrow the
    integration limit by living in a file with a long name.
    """
    results = _results(
        tmp_path,
        ("unit.xml", _xml([("backend.tests.unit.services.test_things", "test_slow", 5.5)])),
    )
    run = _run(results)
    assert run.returncode != 0, (
        "a plain unit test at 5.5 s is over the 4.0 s unit budget even though "
        f"the same duration is legal for integration\n{_out(run)}"
    )


def test_the_gate_reuses_the_audits_classifier(tmp_path: Path) -> None:
    """The classifier, not a path guess, decides the tier.

    This lane's first path-guessing pass over-counted the subject set against
    the classifier's re-measurable 46 over-1.5 s unit ids, because
    ``categorize_test`` sends any test with "gpu" in it to ``integration`` on
    its substring pattern. If
    the gate classified differently from the audit, the two would disagree
    about which tests are even subject to the 4.0 s line. Pinned on a case the
    classifier actually decides: a ``gpu``-named unit test gets the 10.0 s
    integration limit, so 5.5 s is GREEN for it and red for its unit neighbours.
    """
    results = _results(
        tmp_path,
        (
            "unit.xml",
            _xml(
                [
                    (
                        "backend.tests.unit.services.test_gpu_monitor_batch28_12",
                        "test_statement_is_executed_once",
                        5.5,
                    )
                ]
            ),
        ),
    )
    run = _run(results)
    assert run.returncode == 0, (
        "categorize_test routes any 'gpu' test to integration (10.0 s limit); a "
        "path-guessing gate would call this unit and red it at 4.0 — the "
        "classifier-vs-guess tier disagreement this assertion exists to "
        f"prevent\n{_out(run)}"
    )


RTSP_CASE = (
    "backend.tests.unit.services.test_rtsp_test_service.TestRTSPTestService",
    "test_connection_timeout",
)


def test_the_tracked_slow_bucket_keeps_its_sixty_second_cap(tmp_path: Path) -> None:
    """The audit's ``slow`` tier keeps its own 60 s limit — interpretation
    recorded for the reviewer.

    Ruling 74 wanted exemptions in ONE shrink-only file, so the gate judged
    ``slow`` at the unit budget. Ruling 93 deleted the file, and with it the
    only place those ids could live: five tracked-slow members sit over 1.5 s
    in the three shipping corpora — re-measured maxima, NOT the audit's inline
    comments, which are WP1.3-era fossils (self-review F3): rtsp socket
    timeout 6.007 s, r8_s2b import sweep 4.641 s, job_progress
    test_complete_calculates_duration 3.777 s, error_handler 3.474 s,
    job_progress test_duration_after_start 3.430 s. Judged at the 4.0 s unit
    budget the top two are a PERMANENT false-red on main with no exemption
    channel (the three at 3.4-3.8 s would sit permanently in the WARN list).
    The audit's ``SLOW_TEST_PATTERNS`` list is
    itself a human-adjudication channel — an entry needs a measured breach in
    the corpus AND a ``tpa_slow_list`` census entry — so it inherits its 60 s
    cap. Ruling 93 speaks about unit tests; it says nothing to undo the
    audit's tracked-slow treatment for a bucket the classifier does not call
    unit.
    """
    results = _results(tmp_path, ("unit.xml", _xml([(*RTSP_CASE, 6.007)])))
    run = _run(results)
    assert run.returncode == 0, (
        "the tracked-slow rtsp timeout at 6.0 s is under the 60 s tracked cap; "
        "judging it at the unit budget with no baseline file makes every run "
        f"red on main — a gate nobody can merge against\n{_out(run)}"
    )
    assert "rtsp" not in _out(run), (
        f"a non-unit tier must not appear in the unit WARN list either\n{_out(run)}"
    )


def test_a_tracked_slow_test_over_the_cap_is_red(tmp_path: Path) -> None:
    """The cap is a cap, not an erasure: 61 s is red even for tracked-slow."""
    results = _results(tmp_path, ("unit.xml", _xml([(*RTSP_CASE, 61.0)])))
    run = _run(results)
    assert run.returncode != 0, f"61 s is over the 60 s tracked-slow cap\n{_out(run)}"
    assert "60" in _out(run), "the message must state the cap breached"


def test_benchmark_tests_stay_excluded(tmp_path: Path) -> None:
    """The audit's benchmark exclusion carries over.

    Benchmarks measure latency on purpose and the audit already drops them; a
    gate that reddened a deliberate benchmark would be silenced on contact,
    taking the real rule with it. They are excluded from the WARN list too —
    listing them there would train everyone to skim the summary.
    """
    results = _results(
        tmp_path,
        ("unit.xml", _xml([("backend.tests.benchmarks.test_latency", "test_p99", 40.0)])),
    )
    run = _run(results)
    assert run.returncode == 0, f"a benchmark at 40 s is excluded\n{_out(run)}"
    assert "test_p99" not in _out(run), f"excluded means out of the WARN list too\n{_out(run)}"


# --------------------------------------------------------------------------
# Budgets come from env, so the CI step and the tests share one knob.
# --------------------------------------------------------------------------


def test_budgets_are_env_overridable(tmp_path: Path) -> None:
    """One knob for CI and tests, the audit's ``UNIT_TEST_THRESHOLD`` shape.

    Overridability is what lets the Done-when pair be tested at the script's
    real code path instead of at a hard-coded constant, and keeps the owner's
    numbers written in exactly one place in CI.
    """
    results = _results(
        tmp_path,
        ("unit.xml", _xml([("backend.tests.unit.side.test_a", "test_b", 2.0)])),
    )
    tight = _run(results, {"SLEEP_GATE_UNIT_BUDGET": "1.0"})
    assert tight.returncode != 0, f"unit budget 1.0 must red 2.0 s\n{_out(tight)}"
    loose = _run(results, {"SLEEP_GATE_UNIT_BUDGET": "10.0"})
    assert loose.returncode == 0, f"unit budget 10.0 must let 2.0 s pass\n{_out(loose)}"


# --------------------------------------------------------------------------
# Duplicate ids take the MAX; every breach is reported.
# --------------------------------------------------------------------------


def test_duplicate_ids_are_judged_on_the_max(tmp_path: Path) -> None:
    """A parameterised id appears once per invocation, and a shard retry can
    emit the same id twice in one corpus.

    Judging the first sample or the mean would let a test that breached once
    look cheap. The corpus measurement used max-across-runs and so does the
    gate — 4.5 s over 4.0 with the mean (1.67 s) comfortably green.
    """
    results = _results(
        tmp_path,
        (
            "unit.xml",
            _xml(
                [
                    ("backend.tests.unit.rep.test_repeat", "test_three_times", 0.2),
                    ("backend.tests.unit.rep.test_repeat", "test_three_times", 4.5),
                    ("backend.tests.unit.rep.test_repeat", "test_three_times", 0.3),
                ]
            ),
        ),
    )
    run = _run(results)
    assert run.returncode != 0, (
        "the 4.5 s sample is the one that counts; the mean (1.67 s) would pass "
        f"and hide the sleep\n{_out(run)}"
    )


def test_every_breach_is_listed_not_just_the_first(tmp_path: Path) -> None:
    """A gate that stops at the first breach makes the author re-run per test."""
    results = _results(
        tmp_path,
        (
            "unit.xml",
            _xml(
                [
                    ("backend.tests.unit.a.test_a", "test_one", 4.5),
                    ("backend.tests.unit.b.test_b", "test_two", 5.0),
                    ("backend.tests.unit.c.test_c", "test_three", 9.0),
                ]
            ),
        ),
    )
    run = _run(results)
    out = _out(run)
    assert run.returncode != 0
    for name in ("test_one", "test_two", "test_three"):
        assert name in out, f"every breach must be listed, missing {name}: {out}"


# --------------------------------------------------------------------------
# The script's own header carries the numbers (audit-style usage block).
# --------------------------------------------------------------------------


def test_the_script_docstring_records_the_thresholds() -> None:
    """The script's own header carries the numbers (audit-style usage block)."""
    doc = ast.get_docstring(ast.parse(SCRIPT.read_text(encoding="utf-8"))) or ""
    for number in ("4.0", "10.0", "1.5", "60"):
        assert number in doc, f"{number} belongs in the usage text: {doc[:400]}"
    assert "93" in doc, "the header must cite the ruling that set these numbers"


# --------------------------------------------------------------------------
# The script's own DEFAULT_* constants are executed, not just documented
# (self-review F1: every other test injects the full env dict, so a mutant
# of any DEFAULT_* survived 37/37).
# --------------------------------------------------------------------------


def test_the_shipped_defaults_are_the_ruling_93_numbers(tmp_path: Path) -> None:
    """One corpus, no env: the module defaults alone must produce ruling 93's
    verdicts at every tier.

    Why this exists: ``ci.yml`` deliberately sets only four envs — the step's
    comment says ``SLEEP_GATE_SLOW_BUDGET`` stays unset because the 60 s cap
    is the script default — so in production the tracked-slow cap IS
    ``DEFAULT_SLOW_BUDGET``. And an unknown future tier falls to
    ``budgets["unit"]``, which the body's interpretation limb calls "the
    strictest default" — true only while that constant is 4.0. Injecting the
    numbers in every test (as ``_run`` does) measures the injection, not the
    constants; three mutants (slow 60→5, unit 4→2, warn 1.5→3) each survived
    the whole suite before this pin existed.

    Durations chosen so each tier's verdict flips ONLY its own default:
    2.0 s unit (warns at 1.5, green under 4.0 — kills the warn→3.0 mutant and
    the unit→2.0 mutant via the strictness cross-check below), 6.007 s rtsp
    (green at the 60 cap, red at 5 — kills slow→5.0), 5.5 s gpu-classified
    (green at 10.0, red at 2.0 — a second integration/unit witness). The
    header line is asserted too: it PRINTS the budgets, so the numbers are
    read back, not merely inferred from a verdict.
    """
    results = _results(
        tmp_path,
        (
            "unit.xml",
            _xml(
                [
                    (*REDIS_CASE, 2.0),
                    (*RTSP_CASE, 6.007),
                    (
                        "backend.tests.unit.services.test_gpu_monitor_batch28_12",
                        "test_statement_is_executed_once",
                        5.5,
                    ),
                ]
            ),
        ),
    )
    run = _run_defaults(results)
    out = _out(run)
    assert run.returncode == 0, (
        f"with NO env set, the shipped defaults must be exactly ruling 93's "
        f"numbers — every case above is legal under them\n{out}"
    )
    # The header line PRINTS the budgets it used, so the shipped defaults are
    # read back here rather than inferred from a verdict. Formatting is the
    # script's own f-string: unit=4.0s, integration=10.0s, slow=60.0s,
    # warn(unit)=1.5s.
    assert "unit=4.0s" in out, f"unit default must BE 4.0, saw: {out}"
    assert "integration=10.0s" in out, f"integration default must BE 10.0, saw: {out}"
    assert "slow=60.0s" in out, (
        "the 60 s tracked-slow default is load-bearing: ci.yml leaves "
        f"SLEEP_GATE_SLOW_BUDGET unset ON PURPOSE, saw: {out}"
    )
    assert "warn(unit)=1.5" in out, f"the 1.5 s WARN default is ruling 93's own number, saw: {out}"
    assert f"{REDIS_CASE[1]}" in out and "WARN" in out, (
        "a 2.0 s unit test must sit in the WARN band produced by the DEFAULT "
        f"warn budget — a warn-default of 3.0 hides it\n{out}"
    )


def test_the_default_unit_budget_is_the_strictest(tmp_path: Path) -> None:
    """The unknown-tier limb, executed: the unit default is the floor the
    fall-through lands on. ``budget_for`` sends unrecognised tiers to
    ``budgets["unit"]``; 'strictest sensible default' is only true if 4.0 is
    under every other default, asserted from the constants the script ships.
    """
    src = SCRIPT.read_text(encoding="utf-8")

    def _const(name: str) -> float:
        line = next(entry for entry in src.splitlines() if entry.startswith(name))
        return float(line.split("=")[1].strip())

    unit = _const("DEFAULT_UNIT_BUDGET")
    for other in ("DEFAULT_INTEGRATION_BUDGET", "DEFAULT_E2E_BUDGET", "DEFAULT_SLOW_BUDGET"):
        assert unit <= _const(other), (
            f"unknown tiers fall to the unit budget ({unit}); if it stopped "
            f"being the strictest ({other}={_const(other)}), the "
            "strictest-default claim in the docstring is false"
        )
    assert _const("DEFAULT_WARN_BUDGET") < unit, (
        "the WARN default must stay under the hard unit default or the "
        "warn band is empty by construction"
    )


# --------------------------------------------------------------------------
# Self-review N4 (round 2): the two promises a mutation probe proved
# UNPINNED. Both mutants survived the whole suite, so neither limb was
# coverage — reproduced in this lane's shell before either test was written.
# --------------------------------------------------------------------------


def test_exactly_at_a_budget_is_not_a_breach(tmp_path: Path) -> None:
    """Ruling 93's word is "over", and "over" means STRICTLY over.

    M9 (mutant, survived before this test): flipping the breach predicate
    ``duration > budget_for(...)`` to ``>=`` passed the whole suite — no test
    placed a testcase at exactly a budget, so "over 4.0" vs "4.0 or more" was
    adjudicated by nothing. This corpus makes the pair do the work: 4.0 s
    sits exactly on the unit budget, 3.95 s just under it. Correctly, the run
    is GREEN and the WARN list's TOP entry is the 3.95 s test — under ``>=``
    the 4.00 s test is instead a BREACH, rc=1, and heads the report. The
    discriminator is the entry AT the budget, not the list's existence, so
    both list entries must be asserted by identity.
    """
    results = _results(
        tmp_path,
        (
            "unit.xml",
            _xml(
                [
                    ("backend.tests.unit.edge.test_edge", "test_at_the_line", 4.0),
                    ("backend.tests.unit.edge.test_edge", "test_under_the_line", 3.95),
                ]
            ),
        ),
    )
    run = _run(results)
    out = _out(run)
    assert run.returncode == 0, (
        "a unit test at EXACTLY 4.0 s is not OVER 4.0 s — ruling 93's word "
        f"is 'over'; rc!=0 here means the boundary closed to >=\n{out}"
    )
    assert "BREACH" not in out, f"nothing here is over budget; BREACH in output means >=\n{out}"
    # The gate prints each WARN as a duration line then an id line, so the
    # rows are checked in that shape: both tests listed (the boundary test
    # is still over 1.5 s), at their own durations, and the 4.00 row — not a
    # BREACH row — is where the pair lands under a correct gate.
    assert "WARN 4.00s" in out, (
        f"the 4.00 s test must WARN, not breach — the WARN row is the proof "
        f"the boundary held. saw:\n{out}"
    )
    assert "test_at_the_line" in out and "WARN 3.95s" in out, f"pair must both warn:\n{out}"


def test_exactly_at_the_warn_budget_is_not_warned(tmp_path: Path) -> None:
    """The same strictness at the WARN line: "over 1.5 s", so exactly 1.5 is
    silent.

    The warn predicate (``duration > warn_budget``) shares M9's shape. The
    pair is 1.50 s (AT the line — must not appear) with 1.55 s (over it —
    must appear): the 1.55 row is the positive witness that the WARN tier
    is running at all, so the absence check can't be satisfied by a WARN
    tier that lists nothing. (First draft paired 1.50 with 1.45 and the
    file's own run caught it — 1.45 < 1.5 warns nothing, leaving the
    absence assertion vacuous. Pair ABOVE the line, not below.)
    """
    results = _results(
        tmp_path,
        (
            "unit.xml",
            _xml(
                [
                    ("backend.tests.unit.edge.test_edge", "test_at_warn_line", 1.5),
                    ("backend.tests.unit.edge.test_edge", "test_over_warn_line", 1.55),
                ]
            ),
        ),
    )
    run = _run(results)
    out = _out(run)
    assert run.returncode == 0, f"both durations are under 4.0 s; nothing here breaches\n{out}"
    assert "WARN 1.55s" in out and "test_over_warn_line" in out, (
        f"the 1.55 s test must be WARNed — the positive witness; saw:\n{out}"
    )
    assert "1.50s" not in out, (
        "a test at exactly the 1.5 s warn budget is not OVER it; a 1.50s "
        f"row in the output means the WARN predicate closed to >=\n{out}"
    )


def test_an_untracked_tier_falls_to_the_strictest_budget() -> None:
    """M8 (mutant, survived before this test): ``budget_for``'s
    ``budgets.get(category, budgets["unit"])`` re-pointed at
    ``budgets["slow"]`` passed the whole suite — the shipped docstring's
    promise that an unknown future tier falls to the STRICTEST budget (a loud
    review conversation, not a silent 60 s exemption) enforced nothing.

    Direct-call only, and that is not a shortcut: writing the CLI version was
    tried first, and the guard in its first draft proved why it cannot exist —
    ``categorize_test`` emits ONLY the five tracked tier names, so no fixture
    id can ever arrive at ``budget_for`` as an untracked category. The
    fallback is reachable exclusively by a future classifier change, which is
    exactly the case the docstring speaks of. So the pin has two limbs:
    (a) untracked names must land on 4.0, and (b) the budget dict must cover
    every tier the classifier CAN emit (benchmark excepted — it is dropped
    before budgeting), which is what makes limb (a)'s scenario a review
    conversation instead of dead code the day the audit grows a tier.
    """
    budgets = {"unit": 4.0, "integration": 10.0, "e2e": 10.0, "slow": 60.0}
    for probe in ("whatever", "future_tier", "unit-adjacent"):
        assert _gate.budget_for(probe, budgets) == budgets["unit"], (
            f"untracked tier {probe!r} must fall to the unit budget (4.0) — "
            "the docstring's 'strictest sensible default'; 60.0 here is the "
            "silent exemption the same docstring forbids"
        )
    # Limb (b): every name categorize_test can return either has its own
    # budget or is benchmark (dropped at parse time, never budgeted). A new
    # tier in the audit reddens THIS assert — the loud conversation, pinned.
    assert set(budgets) | {"benchmark"} == KNOWN_TIERS, (
        f"budgets cover {sorted(budgets)}, classifier emits {sorted(KNOWN_TIERS)}; "
        "a tier in neither place falls silently to the unit budget while "
        "reading like it was accounted for"
    )
    # Structural witness for the mutant itself: the fallback expression
    # resolves to the unit entry in the shipped source.
    src = SCRIPT.read_text(encoding="utf-8")
    fallback = next(
        line for line in src.splitlines() if line.strip().startswith("return budgets.get(")
    )
    assert 'budgets["unit"]' in fallback, (
        f"the fallback target must be the unit budget in the source; saw: {fallback.strip()}"
    )


# ==========================================================================
# UR-125 AS AMENDED (owner design session 2026-10-12, pass 2 Q9): a unit-tier
# breach must REPRODUCE before it goes red.
#
# Verbatim: "The real-sleep gate fails a unit test over 4.0 s only when the
# breach reproduces: the gate re-runs that one test once, in the same job, and
# the run is red only if the re-run also breaches; a test that passes on its
# re-run is listed as a warning with both timings."
#
# The package's three Done-when cases are the first three tests below, plus the
# 1.5-4.0 s clause. Everything after them is the machinery's FAILURE shapes —
# the cases where adding a re-run can make the gate weaker than ruling 93
# left it, which is the only way this amendment can hurt.
#
# **How the re-run is driven without paying a real sleep.** The gate re-invokes
# one test by argv; ``SLEEP_GATE_PYTEST`` replaces that argv prefix (default
# ``<sys.executable> -m pytest``) and each test below points it at a stub
# pytest written into ``tmp_path``, which records every invocation and prints a
# canned duration in the one format the gate parses. The gate's own argv
# construction, junit temp-file handling, parsing and verdict path all still
# run end to end — only the process on the other end of the pipe is canned.
# ``test_the_default_rerun_is_live_and_names_this_interpreter`` then pins the
# DEFAULT against a real test in this repo, because a stubbed seam proves
# nothing about the runner production uses.
#
# **Why the re-run is OFF until the env turns it on, and why that is not the
# downgrade returning through a flag.** ``SLEEP_GATE_RERUN`` can name no test,
# widen no budget and read no previous run, so it is not an exemption channel;
# unset, the gate is ruling 93 byte for byte (breach = red, nothing spawned).
# It exists because a re-run is only meaningful where the checked-out tree is
# the tree that produced the junit: the audit job is that place (same commit,
# same runner, same job — the package's "in the same job"), whereas a junit
# artifact replayed on a laptop would compare two machines and could CLEAR a
# genuine breach. The step sets it and
# ``test_the_gate_step_enables_the_re_run`` makes dropping it an alarm instead
# of a silent reversion. Two more rules the pins below hold: a re-run the gate
# CANNOT complete stays RED (unverified is not passed), and the report says
# which of the three states it is in, so "off" and "broken" never read as "the
# rule".
# ==========================================================================

RERUN_ON = {"SLEEP_GATE_RERUN": "1"}

# A corpus id with NO module behind it: the re-run can never accidentally
# execute something real while these pins are checking the machinery.
SLEEPER = ("backend.tests.unit.slow.test_sleeper", "test_a")
SLEEPER_ID = f"{SLEEPER[0]}::{SLEEPER[1]}"
SLEEPER_TARGET = "backend/tests/unit/slow/test_sleeper.py::test_a"


def _stub_pytest(
    tmp_path: Path,
    durations: dict[str, str],
    *,
    exit_codes: dict[str, int] | None = None,
    collect_zero: set[str] | None = None,
    skipped: set[str] | None = None,
    stalling: set[str] | None = None,
    late: dict[str, tuple[str, float]] | None = None,
    calls_file: Path,
) -> str:
    """A stand-in for ``python -m pytest``: canned duration, canned exit code.

    ``durations`` maps the re-run test's NAME to the seconds its canned junit
    reports, and a name in ``collect_zero`` exits 5 (pytest's real "no tests
    collected"); a name in neither exits 4 with no junit — the "could not run
    it" shape. A name in ``skipped`` exits **0** and writes a real skip
    (``<skipped/>`` child, ``skipped="1"``, a tiny nonzero ``time``): that is
    what pytest does when a ``skipif`` guard no longer holds on the box doing
    the re-run, and it is the one degraded-env shape that exits successfully.

    **Keyed by name, deliberately not by the path target.** Keying by target
    would mean the helper has to build the expected ``path::name`` itself, and
    a helper that re-derives the path re-implements the very inversion
    ``test_the_re_run_names_the_breaching_test_as_a_path`` exists to check —
    an inverted id would then match the fixture's own wrong spelling and every
    machinery pin below would go green on a gate that can never re-run
    anything. So the stub answers "whatever you asked for, this is how long it
    took" and leaves the target string as data only that one pin reads. A
    target whose name the stub does not know still exits 4, so the fail-closed
    arms keep their teeth.

    It writes its junit to whatever ``--junit-xml=`` the gate passed, so the
    gate's temp-file handling is on the path under test, and appends every
    invocation to ``calls_file`` so a pin can assert *once*, and with what.

    ``stalling`` names hang forever instead of answering: that is what a
    collection-time stall looks like (a module-level import that never
    returns), and it is the one shape the re-run's own ``--timeout`` CANNOT
    stop, because pytest-timeout arms per test item and there is no item yet.
    Every other arm here finishes on its own; only the parent bound can end
    this one, so a pin that uses it is really testing the parent bound and not
    the child's flag. ``late`` answers with a valid junit after a delay — the
    child-slow-but-legitimate path the grace exists to leave alone.
    """

    def name_of(key: str) -> str:
        """``a.b.c::test_x`` and ``path::Class::test_x`` both → ``test_x``."""
        return key.rsplit("::", maxsplit=1)[-1]

    # Projected HERE rather than inside the f-string: an f-string replacement
    # field parses its expression as real Python, where ``{{}}`` is not an
    # escaped empty dict but a set literal holding one (TypeError: unhashable).
    by_name = {name_of(k): v for k, v in durations.items()}
    by_exit = {name_of(k): v for k, v in (exit_codes or {}).items()}
    by_zero = sorted(name_of(k) for k in (collect_zero or set()))
    by_skip = sorted(name_of(k) for k in (skipped or set()))
    by_stall = sorted(name_of(k) for k in (stalling or set()))
    by_late = {name_of(k): v for k, v in (late or {}).items()}
    script = tmp_path / "stub-pytest.py"
    script.write_text(
        textwrap.dedent(
            f"""\
            import json, os, sys
            argv = sys.argv[1:]
            D = {by_name!r}
            EXIT = {by_exit!r}
            ZERO = {by_zero!r}
            SKIP = {by_skip!r}
            STALL = {by_stall!r}
            LATE = {by_late!r}
            target = next((a for a in argv if "::" in a), "")
            name = target.split("::")[-1]
            xml = next((a.split("=", 1)[1] for a in argv if a.startswith("--junit-xml=")), "")
            with open({str(calls_file)!r}, "a", encoding="utf-8") as h:
                h.write(json.dumps({{"argv": argv, "cwd": os.getcwd()}}) + "\\n")
            if name in STALL:
                import time
                while True:
                    time.sleep(3600)
            if name in LATE:
                import time
                t, delay = LATE[name]
                time.sleep(delay)
                if xml:
                    with open(xml, "w", encoding="utf-8") as h:
                        h.write(
                            '<?xml version="1.0" encoding="utf-8"?>'
                            '<testsuites name="pytest tests"><testsuite name="pytest" tests="1" '
                            'failures="0" errors="0" skipped="0" time="' + t + '">'
                            '<testcase classname="" name="x" time="' + t + '" /></testsuite>'
                            "</testsuites>"
                        )
                sys.exit(0)
            if name in ZERO:
                sys.exit(5)
            if name in SKIP:
                # The shape pytest really emits for a skip (measured against
                # this repo's pytest): exit 0, a <skipped/> CHILD, and a tiny
                # but NONZERO time. The nonzero part is what makes this a bug
                # rather than a trivially-empty row — the gate's "is there a
                # usable duration" test passes on it, so only the skipped
                # marker can stop the clearance.
                if xml:
                    with open(xml, "w", encoding="utf-8") as h:
                        h.write(
                            '<?xml version="1.0" encoding="utf-8"?>'
                            '<testsuites name="pytest tests"><testsuite name="pytest" tests="1" '
                            'failures="0" errors="0" skipped="1" time="0.035">'
                            '<testcase classname="" name="x" time="0.035">'
                            '<skipped type="pytest.skip" message="no db in this env">'
                            "skipped</skipped></testcase></testsuite>"
                            "</testsuites>"
                        )
                sys.exit(0)
            if name not in D:
                print(f"ERROR: no tests ran for {{target}}", file=sys.stderr)
                sys.exit(4)
            t = D[name]
            if xml:
                with open(xml, "w", encoding="utf-8") as h:
                    h.write(
                        '<?xml version="1.0" encoding="utf-8"?>'
                        '<testsuites name="pytest tests"><testsuite name="pytest" tests="1" '
                        'failures="0" errors="0" skipped="0" time="' + t + '">'
                        '<testcase classname="" name="x" time="' + t + '" /></testsuite>'
                        "</testsuites>"
                    )
            sys.exit(EXIT.get(name, 0))
            """
        ),
        encoding="utf-8",
    )
    return f"{sys.executable} {script}"


def _calls(calls_file: Path) -> list[dict]:
    """Every recorded stub invocation, as ``{"argv": [...], "cwd": "..."}``.

    A dict and not a bare argv because the child's working directory is
    load-bearing (the re-run target is repo-relative) and nothing else
    observes it.
    """
    if not calls_file.exists():
        return []
    return [
        json.loads(line)
        for line in calls_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _argvs(calls_file: Path) -> list[list[str]]:
    return [rec["argv"] for rec in _calls(calls_file)]


def test_a_breach_that_passes_its_re_run_is_a_warning_not_red(tmp_path: Path) -> None:
    """Done-when case 1 — "the run is red only if the re-run also breaches".

    4.5 s in the corpus, 0.4 s on the re-run: the runner-starvation shape the
    amendment exists to forgive. GREEN, and listed.
    """
    calls = tmp_path / "calls.jsonl"
    results = _results(tmp_path, ("unit.xml", _xml([(*SLEEPER, 4.5)])))
    run = _run(
        results,
        {
            **RERUN_ON,
            "SLEEP_GATE_PYTEST": _stub_pytest(tmp_path, {SLEEPER_ID: "0.4"}, calls_file=calls),
        },
    )
    out = _out(run)
    assert run.returncode == 0, (
        f"a breach that does NOT reproduce is a warning, not a red — that IS the amendment\n{out}"
    )
    assert "BREACH" not in run.stdout, f"a non-reproducing breach must not print as one\n{out}"
    assert "WARN" in out and SLEEPER[1] in out, (
        f"the non-reproducing breach must be listed as a warning\n{out}"
    )
    invoked = _calls(calls)
    assert len(invoked) == 1, (
        "exactly ONE re-run of the one breaching test — 're-runs that one test "
        f"once' is the ruling's word; a retry loop is a different rule: {invoked}"
    )


def test_the_warning_row_after_a_clean_re_run_carries_both_timings(tmp_path: Path) -> None:
    """Done-when case 2 — "a warning WITH BOTH TIMINGS", not the flattering one.

    A row showing only ``0.40s`` reads as "this test is fine" and the 4.5 s
    event leaves the record, which is the downgrade the owner did not grant.
    Both numbers, in stdout and in ``$GITHUB_STEP_SUMMARY``, beside the same id.
    """
    calls = tmp_path / "calls.jsonl"
    summary = tmp_path / "step-summary.md"
    results = _results(tmp_path, ("unit.xml", _xml([(*SLEEPER, 4.5)])))
    run = _run(
        results,
        {
            **RERUN_ON,
            "SLEEP_GATE_PYTEST": _stub_pytest(tmp_path, {SLEEPER_ID: "0.4"}, calls_file=calls),
            "GITHUB_STEP_SUMMARY": str(summary),
        },
    )
    out = _out(run)
    assert run.returncode == 0, f"expected green; got\n{out}"
    row = next(line for line in out.splitlines() if SLEEPER[1] in line)
    assert "4.50" in row and "0.40" in row, (
        f"the row must carry the corpus AND the re-run timing; saw: {row!r}"
    )
    written = summary.read_text(encoding="utf-8")
    line2 = next((line for line in written.splitlines() if SLEEPER_ID in line), "")
    assert "4.50" in line2 and "0.40" in line2, (
        "both timings belong in the step summary too — that is where the owner "
        f"reads the numbers\n{written}"
    )


def test_a_cleared_unit_breach_is_listed_once_not_twice(tmp_path: Path) -> None:
    """Review finding 2: the dedup half of ``cleared_rows_outside_warns`` is load-bearing.

    A unit breach is over the 1.5 s warn threshold by arithmetic, so WARNS
    already holds it, and ``cleared_rows_outside_warns`` must NOT also hand it
    to the "did not reproduce" section — that predicate
    (``test_id not in already_listed``) is what keeps it one row. Measured on
    this PR's head: dropping that clause leaves all pre-existing pins green
    (60 passed) and prints the id TWICE on stdout (WARN row + DID NOT
    REPRODUCE row) and twice in the summary. Counting the full id is the check
    membership cannot make: the row that exists proves nothing about the row
    that shouldn't.
    """
    calls = tmp_path / "calls.jsonl"
    summary = tmp_path / "step-summary.md"
    results = _results(tmp_path, ("unit.xml", _xml([(*SLEEPER, 4.5)])))
    run = _run(
        results,
        {
            **RERUN_ON,
            "SLEEP_GATE_PYTEST": _stub_pytest(tmp_path, {SLEEPER_ID: "0.4"}, calls_file=calls),
            "GITHUB_STEP_SUMMARY": str(summary),
        },
    )
    out = _out(run)
    assert run.returncode == 0, f"cleared breach is green; got\n{out}"
    assert out.count(SLEEPER_ID) == 1, (
        f"a cleared UNIT breach gets exactly ONE stdout row (the WARN row); "
        f"the dedup predicate put it in the did-not-reproduce section too\n{out}"
    )
    written = summary.read_text(encoding="utf-8")
    assert written.count(SLEEPER_ID) == 1, (
        "one row in the step summary as well — a double-list is what the "
        f"owner reads as two events\n{written}"
    )


def test_a_breach_that_breaches_again_is_red(tmp_path: Path) -> None:
    """Done-when case 3 (UR-125 + UR-126) — the reproduced breach is RED.

    Durations are the redis backoff's own recorded pair (4.31 s on main, 4.68 s
    locally), the test the amendment was argued over. UR-126: the remedy is in
    the test, so the verdict must still name and size it and show both
    measurements.
    """
    calls = tmp_path / "calls.jsonl"
    results = _results(tmp_path, ("unit.xml", _xml([(*SLEEPER, 4.5)])))
    run = _run(
        results,
        {
            **RERUN_ON,
            "SLEEP_GATE_PYTEST": _stub_pytest(tmp_path, {SLEEPER_ID: "4.7"}, calls_file=calls),
        },
    )
    out = _out(run)
    assert run.returncode != 0, f"a reproduced breach is red, UR-126\n{out}"
    assert "BREACH" in run.stdout and SLEEPER[1] in run.stdout, (
        f"the confirmed breach must still be named\n{out}"
    )
    assert "4.50" in out and "4.70" in out, (
        f"a confirmed breach should show both measurements; the remedy needs them\n{out}"
    )
    assert len(_calls(calls)) == 1, f"one re-run, then the verdict: {_calls(calls)}"


def test_a_1p5_to_4p0_second_unit_test_warns_only_and_is_never_re_run(tmp_path: Path) -> None:
    """Done-when case 4 — "any unit test over 1.5 s is listed as a warning that
    never fails the run", and the re-run must not touch it.

    The re-run is a defence against a FALSE breach; a warn-band test is not a
    breach. Re-running the warn tier would (a) pay a real sleep per warning —
    the shipping corpora hold dozens of ids over 1.5 s — and (b) hand those ids
    a channel to be *erased* from the list by a fast re-run, which is the
    exemption the ruling refuses to grant. So the load-bearing assert is on the
    calls file, not the verdict.
    """
    calls = tmp_path / "calls.jsonl"
    results = _results(
        tmp_path,
        ("unit.xml", _xml([("backend.tests.unit.band.test_mid", "test_mid", 2.5)])),
    )
    run = _run(
        results,
        {**RERUN_ON, "SLEEP_GATE_PYTEST": _stub_pytest(tmp_path, {}, calls_file=calls)},
    )
    out = _out(run)
    assert run.returncode == 0, f"a 2.5 s unit test is warn-only\n{out}"
    assert "WARN" in out and "test_mid" in out, f"and it must be listed\n{out}"
    assert _calls(calls) == [], (
        "a WARN-band test must not be re-run — a fast re-run would delete a "
        f"warning the ruling says must stay listed: {_calls(calls)}"
    )


def test_the_re_run_names_the_breaching_test_as_a_path(tmp_path: Path) -> None:
    """The id must be inverted correctly, or the whole mechanism is inert.

    junit's classname is dotted (``backend.tests.unit.slow.test_sleeper``) and
    a pytest target is a path (``backend/tests/unit/slow/test_sleeper.py``). An
    inversion bug makes every re-run fail with "no tests ran", so the gate
    reports "could not verify" forever, looks rigorous, and never downgrades a
    thing. That failure mode is otherwise indistinguishable from a working gate
    that simply has no flukes; this pin sees the target string itself.
    """
    calls = tmp_path / "calls.jsonl"
    results = _results(tmp_path, ("unit.xml", _xml([(*SLEEPER, 4.5)])))
    run = _run(
        results,
        {
            **RERUN_ON,
            "SLEEP_GATE_PYTEST": _stub_pytest(tmp_path, {SLEEPER_ID: "0.4"}, calls_file=calls),
        },
    )
    assert run.returncode == 0, _out(run)
    argv = _argvs(calls)[0]
    target = next(a for a in argv if "::" in a)
    assert target == SLEEPER_TARGET, (
        f"target must be the corpus id inverted to path::name; saw {target!r}"
    )


def test_the_re_run_clears_addopts_and_sets_its_own_timeout(tmp_path: Path) -> None:
    """The re-run must measure what the budget speaks about.

    Two ini settings would poison a re-run, from two different places, cleared
    by two different mechanisms — and an earlier revision of this docstring
    credited both to ``addopts``, which is wrong twice over. ``addopts``
    (``pyproject.toml:545``) carries ``-n 8 --dist=worksteal``; inheriting that
    would time the sleep under 8-way runner contention — the exact starvation
    the amendment forgives, so a genuine breach would be *confirmed* by the
    contention that disguised it. ``timeout = 5`` is its OWN ini key
    (``pyproject.toml:546``, not inside ``addopts``); inherited, pytest-timeout
    kills any re-run over 5 s and reports that as the verdict, making the
    plugin's ceiling, not the owner's 4.0 s, the thing that decides red.

    What clears them must therefore be asserted as what it is: ``-o addopts=``
    present in the argv (the cause of the parallelism being gone — an
    absence-only assertion could not tell "override present" from "override
    deleted", since under the stub nothing re-adds ``-n 8`` on its own), and an
    explicit ``--timeout=`` above the budget (the cause of the ini key being
    overridden — a command-line flag outranks an ini value only by being there).
    """
    calls = tmp_path / "calls.jsonl"
    results = _results(tmp_path, ("unit.xml", _xml([(*SLEEPER, 4.5)])))
    run = _run(
        results,
        {
            **RERUN_ON,
            "SLEEP_GATE_PYTEST": _stub_pytest(tmp_path, {SLEEPER_ID: "4.7"}, calls_file=calls),
        },
    )
    assert run.returncode != 0, _out(run)
    argv = _argvs(calls)[0]
    joined = " ".join(argv)
    assert any(argv[i : i + 2] == ["-o", "addopts="] for i in range(len(argv) - 1)), (
        "the re-run must carry the addopts override as a PAIR, not merely look "
        f"unparallelised (nor hold its two tokens apart, which pytest would "
        f"read as one -o value and a stray test path): {argv}"
    )
    assert "-n 8" not in joined and "--dist" not in joined, (
        "the re-run must not inherit the parallel addopts — it would measure "
        f"contention, not the test: {argv}"
    )
    assert any(a.startswith("--timeout=") for a in argv), (
        "the re-run needs an explicit timeout — timeout=5 is its own ini key "
        f"(pyproject.toml:546), not part of addopts: {argv}"
    )
    timeout = next(a for a in argv if a.startswith("--timeout=")).split("=", 1)[1]
    assert float(timeout) > 4.0, f"the timeout must not undercut the budget: {timeout}"


def test_a_re_run_the_gate_cannot_start_stays_red(tmp_path: Path) -> None:
    """Fail closed on the re-run: "could not check" is not "passed".

    The test is not in the tree (exit 4 — what a renamed or deleted test looks
    like). Nothing about this run says the duration was a fluke. A gate that
    turns unverifiable breaches green has been switched off by the machinery
    meant to explain them — the same WP0.5 doctrine the corpus-level pins apply
    to zero evidence. And the report must say WHY it stayed red.
    """
    calls = tmp_path / "calls.jsonl"
    results = _results(tmp_path, ("unit.xml", _xml([(*SLEEPER, 4.5)])))
    run = _run(
        results,
        {**RERUN_ON, "SLEEP_GATE_PYTEST": _stub_pytest(tmp_path, {}, calls_file=calls)},
    )
    out = _out(run)
    assert run.returncode != 0, (
        "an unverifiable breach is RED; the alternative is a gate that goes "
        f"green because its own re-run is broken\n{out}"
    )
    assert "BREACH" in run.stdout, f"the breach is still the headline\n{out}"
    assert SLEEPER[1] in out and "not verified" in out.lower(), (
        f"the report must say why it stayed red, not just that it did\n{out}"
    )


def test_a_stalling_re_run_is_killed_and_stays_red(tmp_path: Path) -> None:
    """A re-run that never finishes is bounded by the GATE, not by the job.

    This is the shape the child's own ``--timeout`` cannot stop. pytest-timeout
    arms a timer per test item, during runtest; a module that stalls at import
    time never gets to runtest, so there is no timer to fire (measured on this
    repo's pytest: a 12.4 s import stall re-run with ``--timeout=3`` exits 0,
    "1 passed", after 13.4 s of wall clock, reporting ``time="0.023"``). The
    stub here ignores ``--timeout`` on purpose and answers nothing at all, so
    the only thing that can end the wait is the parent bound — which is what
    this pins. Before it, the reaper was the job's own ``timeout-minutes: 15``:
    the run got cancelled, so the audit posted no report and lost every finding
    it had already made to explain one flake.

    Timing is asserted as a FLOOR as well as a ceiling. The floor is the whole
    point: ``timeout=_repro_timeout()`` with no grace would satisfy a ceiling
    alone, and would also cut off the legitimate child-slow path that
    ``test_a_re_run_that_is_slow_but_finishes_is_never_mistaken_for_a_stall``
    pins.
    """
    calls = tmp_path / "calls.jsonl"
    results = _results(tmp_path, ("unit.xml", _xml([(*SLEEPER, 4.5)])))
    started = time.monotonic()
    run = _run(
        results,
        {
            **RERUN_ON,
            "SLEEP_GATE_RERUN_TIMEOUT": "1",
            "SLEEP_GATE_RERUN_GRACE": "1",
            "SLEEP_GATE_PYTEST": _stub_pytest(
                tmp_path, {}, stalling={SLEEPER_ID}, calls_file=calls
            ),
        },
    )
    elapsed = time.monotonic() - started
    out = _out(run)

    assert run.returncode != 0, "a re-run that measured nothing cannot clear the breach\n" + out
    assert "BREACH" in run.stdout, f"the breach is still the headline\n{out}"
    assert "TIMED OUT" in out, (
        "the report must NAME the reason. The generic arm would print "
        f'"pytest exit 91", a number pytest has no meaning for — the same trap '
        f"the SKIPPED row exists to avoid\n{out}"
    )
    assert "could not start" not in out, (
        "a hang is not a failure to launch; collapsing them loses the "
        f"diagnosis the reader needs\n{out}"
    )
    assert 2.0 <= elapsed < 15.0, (
        f"bound = timeout(1) + grace(1) = 2 s, so ~2 s + interpreter startup; "
        f"took {elapsed:.2f}s. Under 2.0 the bound is firing before the child "
        f"gets its own chance; over 15 it is not firing at all\n{out}"
    )
    assert len(_calls(calls)) == 1, (
        "the timeout is not a retry — one re-run, bounded. A second "
        f"invocation would double the worst case\n{out}"
    )


def test_a_re_run_that_is_slow_but_finishes_is_never_mistaken_for_a_stall(
    tmp_path: Path,
) -> None:
    """The grace has to actually be there, or the bound is a new bug.

    A parent bound set equal to ``--timeout`` would kill every child that
    legitimately uses its full allowance and then takes a moment to write the
    junit and tear down — turning the new safety net into a machine that calls
    a slow-but-successful re-run "not verified", which is exactly the red this
    clause exists to remove. So the child answers 2.5 s into a
    timeout(1)+grace(3)=4 s bound: inside it, and past the child's own flag.
    """
    calls = tmp_path / "calls.jsonl"
    results = _results(tmp_path, ("unit.xml", _xml([(*SLEEPER, 4.5)])))
    run = _run(
        results,
        {
            **RERUN_ON,
            "SLEEP_GATE_RERUN_TIMEOUT": "1",
            "SLEEP_GATE_RERUN_GRACE": "3",
            "SLEEP_GATE_PYTEST": _stub_pytest(
                tmp_path, {}, late={SLEEPER_ID: ("0.40", 2.5)}, calls_file=calls
            ),
        },
    )
    out = _out(run)
    assert run.returncode == 0, (
        "a re-run that finished under budget must still be a clearance — the "
        f"grace must not shorten the child's own allowance\n{out}"
    )
    assert "TIMED OUT" not in out, f"the child finished; nothing timed out\n{out}"
    assert "0.40s" in out, (
        "the re-run's own measured duration must still reach the report, which "
        f"is what proves the junit was read and not abandoned\n{out}"
    )


def test_a_re_run_that_SKIPS_stays_red(tmp_path: Path) -> None:
    """A re-run that SKIPS executed nothing, and an executed nothing is not a witness.

    This is the one degraded-environment shape that exits 0. The audit job
    carries no ``services:`` block and no ``DATABASE_URL`` (``unit-tests`` has
    both), and unit tests here skip on environment — GPU, docker daemon, a file
    the job may not check out. So a breach whose re-run hits a ``skipif`` that
    no longer holds on the audit runner returns ``exit 0`` with a real
    ``<skipped>`` element and a tiny nonzero ``time`` — nonzero because pytest
    still times the fixture teardown (measured 0.035 s against this repo's
    pytest, and the gate prints it as ``0.00s``).

    Before the fix that combination CLEARED the breach: the duration parser
    refuses ``time=0`` but not 0.035, and the exit code is clean, so the corpus
    4.5 s became a warning and the run went GREEN. Measured on the shipped code
    8/8 trials. A test that never ran cannot demonstrate that its recorded
    duration was a fluke — the same doctrine as the exit-4 and exit-5 pins
    above, reached through the one path those pins do not cover.
    """
    calls = tmp_path / "calls.jsonl"
    results = _results(tmp_path, ("unit.xml", _xml([(*SLEEPER, 4.5)])))
    run = _run(
        results,
        {
            **RERUN_ON,
            "SLEEP_GATE_PYTEST": _stub_pytest(
                tmp_path, {SLEEPER_ID: "0.035"}, skipped={SLEEPER_ID}, calls_file=calls
            ),
        },
    )
    out = _out(run)
    assert run.returncode != 0, (
        "a skipped re-run is NOT a pass: the test did not run, so nothing about "
        f"this attempt says the 4.5s was a fluke\n{out}"
    )
    assert "BREACH" in run.stdout, f"the breach is still the headline\n{out}"
    assert "skipped" in out.lower(), (
        f"the report must name the skip as the reason it stayed red\n{out}"
    )


def test_a_re_run_that_collects_nothing_stays_red(tmp_path: Path) -> None:
    """pytest's "no tests collected" (exit 5) is the same non-witness.

    A target that selects zero tests exits successfully while executing
    nothing; counting that as clean would clear every breach whose path
    inversion is subtly wrong.
    """
    calls = tmp_path / "calls.jsonl"
    results = _results(tmp_path, ("unit.xml", _xml([(*SLEEPER, 4.5)])))
    run = _run(
        results,
        {
            **RERUN_ON,
            "SLEEP_GATE_PYTEST": _stub_pytest(
                tmp_path, {}, collect_zero={SLEEPER_ID}, calls_file=calls
            ),
        },
    )
    assert run.returncode != 0, (
        f"a re-run that collected nothing measured nothing — red, not a downgrade\n{_out(run)}"
    )
    assert len(_calls(calls)) == 1, "it did try once; the verdict is still red"


def test_a_re_run_that_reports_no_duration_stays_red(tmp_path: Path) -> None:
    """A runner that exits 0 but records 0 s has not measured anything.

    The corpus side already treats a zero-duration testcase as "not a fast
    test, a skipped one" and fails closed on it; the re-run arm must apply the
    same rule to itself, or "no number" silently means "under budget" and every
    re-run becomes a clearance.
    """
    calls = tmp_path / "calls.jsonl"
    results = _results(tmp_path, ("unit.xml", _xml([(*SLEEPER, 4.5)])))
    run = _run(
        results,
        {
            **RERUN_ON,
            "SLEEP_GATE_PYTEST": _stub_pytest(tmp_path, {SLEEPER_ID: "0"}, calls_file=calls),
        },
    )
    assert run.returncode != 0, (
        f"a re-run that reported no duration cannot certify a pass\n{_out(run)}"
    )


def test_the_re_run_happens_once_per_breach_not_once_per_run(tmp_path: Path) -> None:
    """Three breaches → three re-runs, one each, three distinct targets.

    The ruling says "that one test once", per breach. One shared re-run would
    clear tests it never ran or red tests that were clean; a loop that retried
    until green would be ``pytest-rerunfailures``, which this repo already
    ships and which the owner did not ask the gate to become.
    """
    calls = tmp_path / "calls.jsonl"
    results = _results(
        tmp_path,
        (
            "unit.xml",
            _xml(
                [
                    ("backend.tests.unit.multi", "test_a", 4.5),
                    ("backend.tests.unit.multi", "test_b", 5.5),
                    ("backend.tests.unit.multi", "test_c", 6.5),
                ]
            ),
        ),
    )
    run = _run(
        results,
        {
            **RERUN_ON,
            "SLEEP_GATE_PYTEST": _stub_pytest(
                tmp_path,
                {
                    "backend.tests.unit.multi::test_a": "0.3",
                    "backend.tests.unit.multi::test_b": "0.3",
                    "backend.tests.unit.multi::test_c": "0.3",
                },
                calls_file=calls,
            ),
        },
    )
    assert run.returncode == 0, f"all three came back clean; none is a breach\n{_out(run)}"
    targets = sorted(next(a for a in argv if "::" in a) for argv in _argvs(calls))
    assert len(targets) == 3 and len(set(targets)) == 3, (
        f"one re-run per breaching id, three distinct targets; got {targets}"
    )


def test_the_rerun_is_off_unless_the_env_turns_it_on(tmp_path: Path) -> None:
    """The knob's ABSENCE must not be the downgrade wearing a different hat.

    Two arms on one corpus. Off: ruling 93 exactly — red, and nothing spawned —
    plus a report that SAYS the breach went unreproduced, so the off state
    never reads as the rule. On: the clean re-run downgrades it. If the two
    arms agree in either direction, the knob is not what implements the
    amendment and this pin cannot tell.
    """
    off_calls = tmp_path / "off.jsonl"
    results = _results(tmp_path, ("unit.xml", _xml([(*SLEEPER, 4.5)])))
    off = _run(
        results,
        {
            "SLEEP_GATE_PYTEST": _stub_pytest(tmp_path, {SLEEPER_ID: "0.4"}, calls_file=off_calls),
        },
    )
    assert off.returncode != 0, (
        "with the re-run not enabled the gate is ruling 93: breach = red. If "
        f"this went green the knob silently IS an exemption channel\n{_out(off)}"
    )
    assert _calls(off_calls) == [], f"nothing spawns while off: {_calls(off_calls)}"
    assert "not enabled" in _out(off).lower(), (
        "a breach the gate did not attempt to reproduce must say so\n" + _out(off)
    )

    on_calls = tmp_path / "on.jsonl"
    on = _run(
        results,
        {
            **RERUN_ON,
            "SLEEP_GATE_PYTEST": _stub_pytest(tmp_path, {SLEEPER_ID: "0.4"}, calls_file=on_calls),
        },
    )
    assert on.returncode == 0, (
        "same corpus, knob on: the clean re-run downgrades it — the two arms "
        f"must disagree\n{_out(on)}"
    )


def test_a_non_unit_breach_is_red_without_a_re_run(tmp_path: Path) -> None:
    """Tiers OUTSIDE ``RERUN_TIERS`` keep ruling 93's hard red, no re-run.

    (Reworded per review finding 5: this said "the re-run clause speaks about
    UNIT tests" while ruling 151 had already added integration — the sibling
    integration pins kill the same e2e-joins mutant, so the stale sentence
    described behaviour this file now disproves. The live rule is the SET:
    unit + integration re-run, e2e + slow do not.)

    The audit job has no browser and no ``npm ci``, so re-running an e2e id
    there cannot work, and a 23 s Playwright spec is not runner starvation. If
    the implementation ever offered a re-run to a tier outside the set it would
    spawn a doomed subprocess per e2e failure; the stub knows no target here, so
    an attempt is visible in the calls file.
    """
    calls = tmp_path / "calls.jsonl"
    results = _results(
        tmp_path,
        ("e2e.xml", _xml([("specs/edge_case_matrix.spec.ts", "test_slow_spec", 23.1)])),
    )
    run = _run(
        results,
        {**RERUN_ON, "SLEEP_GATE_PYTEST": _stub_pytest(tmp_path, {}, calls_file=calls)},
    )
    out = _out(run)
    assert run.returncode != 0, f"23.1 s over the 10.0 s e2e limit\n{out}"
    assert _calls(calls) == [], (
        "e2e is outside RERUN_TIERS; an e2e breach cannot be re-run in this "
        f"job and must not try: {_calls(calls)}"
    )


def test_the_default_rerun_is_live_and_names_this_interpreter(tmp_path: Path) -> None:
    """The stubbed seam proves nothing about PRODUCTION's runner, so pin that.

    The failure mode this exists to catch is UR-125 being merged while inert: a
    default argv that cannot start would satisfy every stub pin above, report
    "could not verify" on every breach forever, and read exactly like a working
    gate that happens to see no flakes. Three limbs, each cheap.

    (a) The default argv is ``<this interpreter> -m pytest`` — not a bare
        ``pytest`` that could resolve to something off PATH. The audit job gets
        pytest from ``uv sync --extra dev``, so the gate must re-run with the
        interpreter already running it.
    (b) That interpreter can actually IMPORT pytest, proved by running it
        (``--version``, ~0.2 s). Deliberately not a full in-repo collection:
        measured here, ``pytest --collect-only`` on one tiny in-repo file costs
        3.81 s and running it 5.82 s, because this repo's conftest chain is
        heavy — a live arm that pays that would breach this very gate's 4.0 s
        unit budget (and pytest's own ``timeout = 5``) to prove a point, and
        duration gates here are marker-blind, so ``@pytest.mark.slow`` would not
        save it. What a laptop cannot measure honestly, CI measures for real:
        ``test_the_gate_step_enables_the_re_run`` pins that the job which
        enables the re-run is the job that installs the dev extra.
    (c) The child runs with cwd at the repo root, because the re-run target is
        a repo-RELATIVE path — spawn it from anywhere else and every target
        misses, which is limb (b)'s inert-gate shape arriving by a different
        route.
    """
    direct = _gate.rerun_command()
    assert direct[:2] == [sys.executable, "-m"], (
        f"the default must re-run with THIS interpreter, not PATH's: {direct}"
    )
    assert direct[2] == "pytest", f"…invoked as a module, not an executable: {direct}"

    # Real on purpose: this IS the sanity check — it must actually spawn our own
    # interpreter to prove the re-run's default runner resolves. Fixed argv list,
    # no shell; the check-test-timeouts hook's "# real" token exempts it, and
    # ruff's S603 is ignored for backend/tests/ in pyproject.toml.
    probe = subprocess.run(  # real
        [sys.executable, "-m", "pytest", "--version"],
        capture_output=True,
        text=True,
        check=False,
        cwd=_gate.REPO_ROOT,
    )
    assert probe.returncode == 0, (
        "the default runner's pytest must be importable by the interpreter that "
        f"runs the gate; otherwise every re-run is 'could not verify' and "
        f"UR-125 is inert while reading implemented\n{probe.stderr}"
    )

    calls = tmp_path / "calls.jsonl"
    results = _results(tmp_path, ("unit.xml", _xml([(*SLEEPER, 4.5)])))
    _run(
        results,
        {
            **RERUN_ON,
            "SLEEP_GATE_PYTEST": _stub_pytest(tmp_path, {SLEEPER_ID: "0.4"}, calls_file=calls),
        },
    )
    cwd = _calls(calls)[0]["cwd"]
    assert Path(cwd).resolve() == _gate.REPO_ROOT.resolve(), (
        f"the target is repo-relative, so the spawn must happen at the repo root; "
        f"saw cwd={cwd!r} root={_gate.REPO_ROOT}"
    )


def test_a_breach_whose_re_run_fails_stays_red(tmp_path: Path) -> None:
    """The downgrade is for a test that PASSES on its re-run (UR-125's words).

    A re-run that finishes under budget but exits non-zero — it now fails, or
    errors in its fixture — has not been exonerated, it has been caught. This
    is the shape a "fast" reading could wave through: the gate parses a
    duration, sees 0.9 s < 4.0 s, and if it looked only at the number it would
    call a red test a flake that got lucky. The exit code is part of the
    verdict, not noise around it.
    """
    calls = tmp_path / "calls.jsonl"
    results = _results(tmp_path, ("unit.xml", _xml([(*SLEEPER, 4.5)])))
    run = _run(
        results,
        {
            **RERUN_ON,
            "SLEEP_GATE_PYTEST": _stub_pytest(
                tmp_path, {SLEEPER_ID: "0.9"}, exit_codes={SLEEPER_ID: 1}, calls_file=calls
            ),
        },
    )
    out = _out(run)
    assert run.returncode != 0, (
        "a re-run that FAILS fast did not clear the breach — 'passes on its "
        f"re-run' is the only exoneration the ruling grants\n{out}"
    )
    assert "BREACH" in run.stdout, f"the breach stays the headline\n{out}"
    assert len(_calls(calls)) == 1, "one re-run; a failing test is not retried for luck"


def test_a_class_based_breach_is_re_run_with_the_colon_spelling(tmp_path: Path) -> None:
    """junit spells a class member ``Class.method``; pytest wants ``Class::method``.

    junit's own ids are joined with ``::`` for display, but the classname itself
    can carry a class (``test_file.py::TestLedgerWindow::test_window_stamps`` is
    how pytest writes a class member, and the ledger's ``TestDurationTracking``
    row shows those ids really reach the corpora). A target built by splitting
    on the first dot would produce ``…/test_ledger.py.TestLedgerWindow::…`` and
    select nothing — and per the inert-inversion argument above the gate would
    then look permanently unverifiable rather than obviously broken. (The class
    here is deliberately NOT ``TestDurationTracking``, which is a live
    ``SLOW_TEST_PATTERNS`` member and would classify as ``slow``, not ``unit``.)
    """
    calls = tmp_path / "calls.jsonl"
    classname = "backend.tests.unit.tracked.test_ledger.TestLedgerWindow"
    results = _results(
        tmp_path,
        ("unit.xml", _xml([(classname, "test_window_stamps", 4.5)])),
    )
    run = _run(
        results,
        {
            **RERUN_ON,
            "SLEEP_GATE_PYTEST": _stub_pytest(
                tmp_path,
                {f"{classname}::test_window_stamps": "0.4"},
                calls_file=calls,
            ),
        },
    )
    assert run.returncode == 0, _out(run)
    target = next(a for a in _argvs(calls)[0] if "::" in a)
    assert target == (
        "backend/tests/unit/tracked/test_ledger.py::TestLedgerWindow::test_window_stamps"
    ), f"class members need the :: spelling; saw {target!r}"


# ==========================================================================
# UR-125 AS AMENDED BY RULING 151: the INTEGRATION tier gets the same re-run.
#
# Verbatim (UR-125, docs/uplevel/rules.md): "An integration test over its 10.0 s budget gets
# the same single re-run, and is red only if the re-run also breaches; at most 5
# re-runs per job in each tier."
#
# The block above was written when the clause named only unit tests, and the
# gate still implements exactly that: ``reproduce`` filters ``b[2] == "unit"``.
# So an integration test at 12.4 s is red on the first reading, with no
# reproduction, which is the failure mode ruling 151 exists to fix. Eleven of the
# thirteen pins below are red on `main` for three DIFFERENT reasons, and the
# reasons are why this is a three-site change and not a one-line filter:
#
#   * the verdict itself (nothing re-runs an integration breach);
#   * the REPORTING of a cleared one — the WARN list is unit tier by a deliberate
#     comment (listing a legal 2.6 s banner spec would train everyone to skim),
#     and both the stdout warning row and the step-summary row for a cleared
#     breach are rendered by walking that unit-only list. Widen only the filter
#     and a cleared integration breach drops out of ``red`` WITHOUT appearing
#     anywhere: the owner sees a green run that says nothing about the 12.4 s
#     event, which is the downgrade the ruling did not grant;
#   * the CAP, which slices the POOLED list, so "at most 5 per job in each tier"
#     is silently 5 across all tiers — and because integration breaches are the
#     longest ones in the corpus, a pooled cap spends every re-run on
#     integration and leaves the unit tier with none.
#
# The tiers OUTSIDE the clause (e2e, slow) are pinned too, because "everything
# that is not unit" is NOT what the amendment says and the audit job has no
# browser and no ``npm ci``.
#
# The count sentence above is a MEASUREMENT, not an estimate: main's gate blob
# swapped in for this file's, the below-banner tests run against it, and the red
# ones counted (measured 11 failed / 2 passed at this head — the two greens being
# precisely the pins that assert a constant and assert NON-re-runs, so main
# satisfies them without ever re-running integration, which is reason 1 talking).
# Adding a pin below this line moves the number again; re-measure it the same way
# rather than editing the sentence to taste. An earlier revision carried "six of
# eight", true when written and stale by the next commit — review finding 5.
# ==========================================================================

# An integration id with no module behind it, same reasoning as ``SLEEPER``. The
# tier is doubly determined on purpose: the classname carries "integration" AND
# the corpus file is named ``integration.xml``, so a pin cannot go green because
# one channel accidentally classified it (see the M8 probe note at the top of
# this file). Neither name is a SLOW_TEST_PATTERNS member or a ``.spec.`` path.
INTEGRATION = ("backend.tests.integration.api.test_gateway", "test_integration_gateway_slow_path")
INTEGRATION_ID = f"{INTEGRATION[0]}::{INTEGRATION[1]}"

# 12.4 s against the 10.0 s integration budget: a breach by 2.4 s, which is
# squarely the "runner was starved" size, and well clear of the 4.0 s unit
# budget so it cannot be read as a mis-tiered unit test.
INTEGRATION_BREACH = 12.4
INTEGRATION_CLEARANCE = "0.60"


def test_an_integration_breach_that_passes_its_re_run_is_not_red(tmp_path: Path) -> None:
    """Done-when case 1 for the integration tier (ruling 151, verbatim).

    12.4 s in the corpus, 0.60 s on the re-run: the same shape ruling 122
    forgives in the unit tier. GREEN, one re-run, exactly once.
    """
    calls = tmp_path / "calls.jsonl"
    results = _results(tmp_path, ("integration.xml", _xml([(*INTEGRATION, INTEGRATION_BREACH)])))
    run = _run(
        results,
        {
            **RERUN_ON,
            "SLEEP_GATE_PYTEST": _stub_pytest(
                tmp_path, {INTEGRATION_ID: INTEGRATION_CLEARANCE}, calls_file=calls
            ),
        },
    )
    out = _out(run)
    assert run.returncode == 0, (
        "an integration breach that does NOT reproduce must not fail the run — "
        f"ruling 151 gives this tier the same single re-run\n{out}"
    )
    assert "BREACH" not in run.stdout, f"a non-reproducing breach is not a breach\n{out}"
    invoked = _calls(calls)
    assert len(invoked) == 1, (
        f"one re-run of the breaching id, not zero and not a retry loop: {invoked}"
    )


def test_a_cleared_integration_breach_is_still_listed_with_both_timings(
    tmp_path: Path,
) -> None:
    """The downgrade has to be VISIBLE, or it is an exemption channel.

    A cleared unit breach is over the 1.5 s WARN threshold by arithmetic, so it
    reaches the report for free. A cleared INTEGRATION breach is not: the WARN
    list is unit-tier by a deliberate comment, and today both the stdout row and
    the ``$GITHUB_STEP_SUMMARY`` row for a cleared breach are emitted by walking
    that list. So a gate that widens only the eligibility filter would drop this
    id out of the breach list and print nothing about it — a green run with no
    record of a 12.4 s event, which is the exact "listed as a warning" half of
    UR-125 going missing while the leniency half ships.

    Both numbers, beside the same id, in stdout AND in the step summary: the
    corpus timing is the event, the re-run timing is the exoneration, and a row
    that shows only the flattering one deletes the event.
    """
    calls = tmp_path / "calls.jsonl"
    summary = tmp_path / "step-summary.md"
    results = _results(tmp_path, ("integration.xml", _xml([(*INTEGRATION, INTEGRATION_BREACH)])))
    run = _run(
        results,
        {
            **RERUN_ON,
            "SLEEP_GATE_PYTEST": _stub_pytest(
                tmp_path, {INTEGRATION_ID: INTEGRATION_CLEARANCE}, calls_file=calls
            ),
            "GITHUB_STEP_SUMMARY": str(summary),
        },
    )
    out = _out(run)
    assert run.returncode == 0, f"expected green; got\n{out}"
    assert len(_calls(calls)) == 1, "the re-run has to happen before anything can report it"

    row = next((line for line in run.stdout.splitlines() if INTEGRATION[1] in line), "")
    assert row, (
        "a cleared integration breach must appear in the output at all — it is "
        f"no longer a breach, so silence here means silence everywhere\n{out}"
    )
    assert "12.40" in row and INTEGRATION_CLEARANCE in row, (
        f"the row must carry corpus AND re-run timing; saw: {row!r}"
    )

    written = summary.read_text(encoding="utf-8")
    summary_row = next((line for line in written.splitlines() if INTEGRATION_ID in line), "")
    assert summary_row, (
        "the step summary is where the owner reads this, and a cleared "
        f"integration id is not in the unit WARN list it is built from\n{written}"
    )
    assert "12.40" in summary_row and INTEGRATION_CLEARANCE in summary_row, (
        f"both timings in the summary row too; saw: {summary_row!r}"
    )
    # Review finding 6: the PASS verdict line is what a reader trusts, and a
    # phrasing that says "unit" here is FALSE for this corpus — the only test
    # that was over budget is an integration one. The sentence existed on an
    # earlier revision of this PR and a mutant restores it with every other pin
    # green, so the word itself is pinned now.
    pass_line = next(
        (line for line in run.stdout.splitlines() if line.startswith("RESULT: PASS")), ""
    )
    assert pass_line, f"a cleared run must print its PASS verdict\n{out}"
    assert "unit" not in pass_line, (
        f"nothing unit was cleared here; the verdict must not claim it: {pass_line!r}"
    )
    # Review finding 3: the WORD was pinned, the sentence around it was not.
    # Three mutants ran the whole suite green while lying on exactly this run —
    # a zero count, a dropped exoneration claim, and the bare "no test over its
    # real-sleep budget", which is verbatim the sentence the gate's own comment
    # calls false on this path, because one test WAS over budget here.
    assert "1 test(s) were over budget" in pass_line, (
        f"the green has to say how many it let through: {pass_line!r}"
    )
    assert "no test over its real-sleep budget" not in pass_line, (
        "a cleared run must not claim nothing was ever over budget; the gate's "
        f"own comment calls this exact sentence false here: {pass_line!r}"
    )
    # A bare `"re-run" in pass_line` would pass on a mutant that deletes the
    # exoneration, because the line's FIRST clause already contains the word
    # ("...reproduced on its re-run"). So ask the count clause what happened to
    # the tests it counted: a bare "N test(s) were over budget in the corpus."
    # on a GREEN run reads as an unanswered question. Wording beyond that is
    # free -- "cleared" and "re-run" are alternatives, not a spelling test.
    tail = pass_line.split("were over budget", 1)[1]
    assert "cleared" in tail or "re-run" in tail, (
        f"the count clause must say the over-budget tests were exonerated, not "
        f"just that they existed: {pass_line!r}"
    )
    # Review finding 7: the section header's COUNT was free. A mutant reading
    # len(breaches) where the code reads len(listed_elsewhere) prints "2" above
    # one row — counting the breach that DID reproduce, the single distinction
    # the header's own parenthetical ("listed, never failing") exists to make.
    # Anchored on the section NAME, not on "listed, never failing)", which the
    # unit-WARN header prints too — matching that would test whichever of the two
    # happened to print first. The scan stops at the blank line that closes the
    # section, so it counts THIS section's rows and not the report's.
    lines = run.stdout.splitlines()
    head_i = next(
        i for i, ln in enumerate(lines) if ln.startswith("OVER BUDGET, DID NOT REPRODUCE")
    )
    stated = int(lines[head_i].rsplit(":", 1)[1])
    body = []
    for ln in lines[head_i + 1 :]:
        if ln.strip() == "":
            break
        if ln.startswith("  WARN "):
            body.append(ln)
    assert stated == len(body) == 1, (
        f"one cleared breach is listed here, so the header must state 1 above 1 "
        f"row; stated {stated} above {len(body)}\n{run.stdout}"
    )


def test_an_integration_breach_that_breaches_again_is_red(tmp_path: Path) -> None:
    """Done-when case 2 — "red only if the re-run also breaches".

    Deliberately GREEN on `main`, and it must stay green after the filter
    widens: it is the pin that fails if the integration tier is ever made
    exempt instead of merely re-measured. The re-run reports 13.1 s, over the
    10.0 s budget, so the breach reproduced.
    """
    calls = tmp_path / "calls.jsonl"
    results = _results(tmp_path, ("integration.xml", _xml([(*INTEGRATION, INTEGRATION_BREACH)])))
    run = _run(
        results,
        {
            **RERUN_ON,
            "SLEEP_GATE_PYTEST": _stub_pytest(tmp_path, {INTEGRATION_ID: "13.1"}, calls_file=calls),
        },
    )
    out = _out(run)
    assert run.returncode != 0, (
        f"a 12.4 s breach that re-runs at 13.1 s is real and stays RED\n{out}"
    )
    assert "BREACH" in run.stdout, f"the breach stays the headline\n{out}"
    assert len(_calls(calls)) == 1, "one re-run; a reproduced breach is not retried for luck"
    # The FAIL line names the tiers the re-run covers, and this corpus is
    # INTEGRATION-ONLY, so the wording is load-bearing here: the red branch is
    # shared by every tier, so a revert to the pre-ruling-151 "seconds-scale unit
    # test" would have this integration failure telling the reader to go fix a
    # unit test. That is the same falsehood the PASS-line pin above exists to
    # prevent, and the earlier note here argued the opposite — that any reword
    # "stays true of a two-tier red set" — which is true only of a set that has a
    # unit member in it. UR-89 batch-3 finding 3.3: a revert of this one clause
    # ran the whole suite green (75 passed) before this pin existed.
    assert "in a re-run tier" in out, (
        f"the FAIL line must name the tier the re-run covers; this is an "
        f"integration-only red\n{out}"
    )
    assert "seconds-scale unit test" not in out, (
        f"a red integration test must not be explained as a unit test\n{out}"
    )


# Review finding 1: the exoneration ruling 151 grants lives in the 4.0-10.0 s
# band, and before these two pins NO re-run duration anywhere in this file sat
# inside it (every value was 0 / 0.4 / 4.7 / 13.1), so the comparison
# `elif seconds > budget:` was never distinguished from `seconds > min(budget,
# 4.0)` — that mutant ran the whole suite green while reddening a real 6.00 s
# integration re-run. The greens below sit at 9.90 s, not the reviewer's
# suggested 6.00 s, because 9.90 kills every mutant that lowers the effective
# threshold STRICTLY below 9.9, and 6.00 would survive min(budget, 8.0).
# "strictly" is load-bearing and was added after review: min(budget, 9.9)
# agrees with the base at exactly 9.90 — both clear it — so nothing that stops
# AT 9.9 dies here. That mutant needs the boundary pin below instead.
def test_an_integration_re_run_at_9p90_seconds_is_cleared(tmp_path: Path) -> None:
    """The 4.0-10.0 s band is judged against the INTEGRATION budget, not 4.0 s.

    12.4 s in the corpus, 9.90 s re-run: under the 10.0 s budget, so cleared.
    This is the duration ruling 151 exists to forgive — a starved integration
    test that re-measures just under its own limit. A gate that judged the
    re-run against the 4.0 s unit line would call it CONFIRMED red here.
    """
    calls = tmp_path / "calls.jsonl"
    results = _results(tmp_path, ("integration.xml", _xml([(*INTEGRATION, INTEGRATION_BREACH)])))
    run = _run(
        results,
        {
            **RERUN_ON,
            "SLEEP_GATE_PYTEST": _stub_pytest(tmp_path, {INTEGRATION_ID: "9.9"}, calls_file=calls),
        },
    )
    out = _out(run)
    assert run.returncode == 0, (
        "a re-run at 9.90 s is under the 10.0 s integration budget, so it is "
        "exonerated. If this goes red the re-run is being judged against a "
        f"smaller budget than the tier's own:\n{out}"
    )
    assert "BREACH" not in run.stdout, f"a cleared re-run must not print as a breach\n{out}"
    assert len(_calls(calls)) == 1, f"one re-run, then the verdict: {_calls(calls)}"


def test_an_integration_re_run_at_10p40_seconds_is_red(tmp_path: Path) -> None:
    """The mirror, just over the line: 10.40 s re-run against 10.0 s is RED.

    Without this half the green above is ambiguous — it would also be green on
    a gate that forgives the integration tier entirely. Together the pair
    brackets the judged threshold to (9.90, 10.40], which CONTAINS the 10.0 s
    integration budget, per tier rather than inherited from the unit case.

    A bracket is not a boundary. `seconds >= budget` agrees with `>` at BOTH
    endpoints of that interval and differs from it only at exactly 10.00 s, so
    this pair cannot kill that mutant however tight the bracket gets -- see
    test_an_integration_re_run_at_exactly_the_budget_is_cleared.
    """
    calls = tmp_path / "calls.jsonl"
    results = _results(tmp_path, ("integration.xml", _xml([(*INTEGRATION, INTEGRATION_BREACH)])))
    run = _run(
        results,
        {
            **RERUN_ON,
            "SLEEP_GATE_PYTEST": _stub_pytest(tmp_path, {INTEGRATION_ID: "10.4"}, calls_file=calls),
        },
    )
    out = _out(run)
    assert run.returncode != 0, (
        "a re-run at 10.40 s is over the 10.0 s budget and the breach "
        f"reproduced; a green here means the tier got an exemption\n{out}"
    )
    assert "BREACH" in run.stdout, f"the breach stays the headline\n{out}"
    assert len(_calls(calls)) == 1, "one re-run; a reproduced breach is not retried for luck"


def test_an_integration_re_run_at_exactly_the_budget_is_cleared(tmp_path: Path) -> None:
    """The boundary itself: a re-run AT 10.00 s against a 10.0 s budget CLEARS.

    The 9.90/10.40 pair brackets the threshold but never lands on it, and a
    bracket is not a boundary — `seconds >= budget` clears 9.90 and reddens
    10.40 exactly as the real `>` does, so it runs the entire suite green while
    turning a real 10.00 s re-run RED. Measured at this head with the mutants
    applied IN PLACE to the gate (it imports a sibling script by path, so a
    relocated copy cannot run) and restored under md5: at 10.00 s the base
    clears with exit 0, `>=` exits 1, and `> min(budget, 9.9)` exits 1. One
    duration kills both survivors, which is why this pin sits beside the pair
    rather than replacing it.

    The corpus side has had this shape for a while
    (``test_exactly_at_a_budget_is_not_a_breach``); the re-run side had none.
    """
    calls = tmp_path / "calls.jsonl"
    results = _results(tmp_path, ("integration.xml", _xml([(*INTEGRATION, INTEGRATION_BREACH)])))
    run = _run(
        results,
        {
            **RERUN_ON,
            "SLEEP_GATE_PYTEST": _stub_pytest(tmp_path, {INTEGRATION_ID: "10.0"}, calls_file=calls),
        },
    )
    out = _out(run)
    assert run.returncode == 0, (
        "10.00 s against a 10.0 s budget is not OVER it — the comparison is "
        "`seconds > budget`, so a re-run landing exactly on the limit reproduced "
        f"nothing. This going red means the operator became `>=`:\n{out}"
    )
    assert "BREACH" not in run.stdout, f"an exactly-at-budget re-run is cleared\n{out}"
    assert len(_calls(calls)) == 1, "one re-run; a cleared breach is not retried for luck"


def test_the_cap_value_is_the_number_the_rulebook_states() -> None:
    """The bound itself, asserted against the script instead of read from it.

    The two pins below compare re-run counts to ``_gate.MAX_RERUNS``, which is
    deliberate: they pin the SHAPE (one slice per tier) and keep describing the
    rule if the bound ever moves. The cost of reading it is that they cannot see
    the bound move DOWN — the fixture corpora are sized from the same constant
    (``range(MAX_RERUNS + 1)``) or from a count above it (``range(6)``), so a
    smaller cap shrinks the fixtures and the expectations in step. Measured on
    this PR's head ``25f97f14e``, ``MAX_RERUNS`` = 1, 2, 3 and 4 all leave BOTH
    pins green; only 6 and 7 are caught, and only because the corpus happens to
    hold 6 breaches per tier. So the number UR-125 states was pinned nowhere,
    and a silent 5 -> 4 is a silent loosening of the exoneration the rule grants.

    This is the file's own precedent, not a new idea: ``BUDGETS`` above hardcodes
    4.0 / 10.0 / 1.5 and names ruling 93 beside them. The cap is the one number a
    rule states that this file did not pin absolutely.

    Authority: UR-125 (``docs/uplevel/rules.md``, the UR-125 clause) — "at most 5 re-runs per job in each
    tier", citing rulings 93, 122 and 151. Ruling 151 itself says "At most 5
    re-runs per job, as for unit tests"; the "in each tier" scoping is the
    rulebook's, which is why this pin cites the rule and not the ruling.
    """
    assert _gate.MAX_RERUNS == 5, (
        "UR-125 states 5 re-runs per job in each tier. Raise this only by "
        "widening UR-125 in docs/uplevel/rules.md first — the rule is the "
        f"authority, not this file; the script had {_gate.MAX_RERUNS}"
    )


def test_the_rerun_cap_applies_to_each_tier_separately(tmp_path: Path) -> None:
    """UR-125: "at most 5 re-runs per job **in each tier**" — not 5 pooled.

    MAX_RERUNS+2 unit breaches and MAX_RERUNS+1 integration ones -- deliberately
    ASYMMETRIC, see the fixture -- so over budget in both eligible tiers, and the
    corpus is sorted longest-first, so a cap that
    slices the POOLED list spends all five re-runs on the five longest — which
    are all integration — and leaves the unit tier with none. That is the
    inverted damage: the tier the cap has served since ruling 122 loses its
    exoneration to the tier ruling 151 just added.

    The rule is 5 PER TIER, so 10 ids get re-run and the one dropped per tier is
    the shortest in that tier. ``MAX_RERUNS`` is the bound; the pin above holds it
    to UR-125's number, and the worst-case cost is therefore MAX_RERUNS sleeps per
    eligible tier per job
    — the pins name the bound, so a reviewer who wants 5 pooled sees it here
    rather than inferring it.
    """
    calls = tmp_path / "calls.jsonl"
    # DELIBERATELY ASYMMETRIC (review finding 1): MAX_RERUNS+2 unit against
    # MAX_RERUNS+1 integration, where 6/6 was symmetric. A symmetric corpus
    # cannot witness a tier-label swap — the swapped (count, tier) multiset is
    # identical — so the pair assertion below needs the counts to differ. They
    # are derived from MAX_RERUNS rather than literal so the asymmetry, which is
    # the property, survives the cap moving.
    unit_cases = [
        (f"backend.tests.unit.tiershard.test_u{i}", f"test_u{i}_slow", 4.4 + 0.1 * i)
        for i in range(MAX_RERUNS + 2)
    ]
    integration_cases = [
        (
            f"backend.tests.integration.tiershard.test_i{i}",
            f"test_integration_i{i}_slow",
            10.4 + 1.1 * i,
        )
        for i in range(MAX_RERUNS + 1)
    ]
    n_unit = len(unit_cases)
    n_integration = len(integration_cases)
    assert n_unit != n_integration, (
        "the fixture must stay asymmetric or the pair assertion below cannot see a tier-label swap"
    )
    durations = {f"{c[0]}::{c[1]}": "0.4" for c in unit_cases + integration_cases}
    results = _results(
        tmp_path,
        ("unit.xml", _xml(unit_cases)),
        ("integration.xml", _xml(integration_cases)),
    )
    run = _run(
        results,
        {
            **RERUN_ON,
            "SLEEP_GATE_PYTEST": _stub_pytest(tmp_path, durations, calls_file=calls),
        },
    )
    out = _out(run)
    invoked = _calls(calls)
    targets = [next((a for a in rec["argv"] if "::" in a), "") for rec in invoked]

    re_run_unit = [t for t in targets if "/unit/" in t]
    re_run_integration = [t for t in targets if "/integration/" in t]
    assert len(re_run_unit) == MAX_RERUNS, (
        f"the unit tier gets its OWN {MAX_RERUNS} re-runs; a pooled cap gave it "
        f"{len(re_run_unit)} because the integration breaches are longer\n{targets}"
    )
    assert len(re_run_integration) == MAX_RERUNS, (
        f"the integration tier gets {MAX_RERUNS} too — 'in each tier' is UR-125's "
        f"wording, and it is what separates 5-per-tier from a 5 total\n{targets}"
    )
    assert len(invoked) == 2 * MAX_RERUNS, f"no tier may exceed the cap either way: {targets}"
    # The cap must still be the STRICT end: the dropped id is the SHORTEST in its
    # tier, and the tier's remaining breaches stay RED unverified.
    assert run.returncode != 0, (
        f"2 of {n_unit + n_integration} breaches are unverified, so this run is RED "
        f"whatever the cap "
        f"decides to re-run\n{out}"
    )
    # The cap has to stay the STRICT end in each tier: what it drops is the
    # SHORTEST breach of that tier, and the longest one must never be the loser.
    unit_names = [t.rsplit("::", 1)[-1] for t in re_run_unit]
    assert "test_u5_slow" in unit_names, (
        f"u5 is the longest unit breach (4.9 s) and must be re-run first; saw {unit_names}"
    )
    assert "test_u0_slow" not in unit_names, (
        f"u0 is the SHORTEST unit breach (4.4 s); dropping anything else would "
        f"make the cap lenient instead of strict; saw {unit_names}"
    )
    # Review finding 6: which ids got re-run was pinned; the report's own PROSE
    # about the cap was free to be deleted. A 6/6 corpus is over the cap in BOTH
    # eligible tiers, so the stderr note must name each of them — a reader
    # told "6 breaches, 5 re-run" without the tier cannot tell which tier lost.
    notes = [line for line in run.stderr.splitlines() if "stay RED unverified" in line]
    assert len(notes) == 2, (
        f"one over-cap note per tier that is over the cap (both here); saw {notes!r}"
    )
    # Review finding 1: membership cannot see a tier-label SWAP, and on the old
    # 6/6 corpus it could not see one AT ALL. So parse the note and assert the
    # PAIR. The explicit len() check is part of the teeth: a gate that stops
    # printing the note in the expected shape would leave `pairs` empty, and an
    # empty set is a very easy thing to assert nothing about.
    parsed = re.findall(r"note: (\d+) (\w+) breaches", "\n".join(notes))
    assert len(parsed) == 2, f"both notes must match the expected shape: {notes!r}"
    pairs = {(int(n), t) for n, t in parsed}
    assert pairs == {(n_unit, "unit"), (n_integration, "integration")}, (
        f"each note must state ITS tier's own breach count; the corpus is "
        f"{n_unit} unit / {n_integration} integration, saw {sorted(pairs)}\n{notes!r}"
    )
    # And the number the note must NOT state: MAX_RERUNS. "5 breaches, only the
    # 5 slowest" describes a corpus where nothing was dropped, in a run that is
    # leaving a breach RED unverified.
    for count, tier in parsed:
        assert int(count) != MAX_RERUNS, (
            f"the {tier} note counts {count} on a tier over the cap; a note that "
            f"equals the cap claims nothing was dropped\n{notes!r}"
        )


def test_a_corpus_sitting_exactly_at_the_cap_prints_no_over_cap_note(tmp_path: Path) -> None:
    """At MAX_RERUNS per tier NOTHING was dropped, so no note may print.

    The cap pin's corpus is deliberately over the cap in both tiers, which pins
    what the note says and nothing about when it appears. A `>=` trigger is
    indistinguishable there — both tiers are over the cap regardless — and it is
    not harmless: it tells the reader "only the 5 slowest get a re-run; the rest
    stay RED unverified" about a run in which every breach got its re-run and the
    job is GREEN. An alarm that fires on a corpus with nothing to alarm about is
    the shape that teaches people to skim the report.

    MAX_RERUNS breaches per eligible tier, every one of them cleared: the strict
    `>` prints no note and exits 0.
    """
    calls = tmp_path / "calls.jsonl"
    unit_cases = [
        (f"backend.tests.unit.atcap.test_u{i}", f"test_u{i}_slow", 4.4 + 0.1 * i)
        for i in range(MAX_RERUNS)
    ]
    integration_cases = [
        (f"backend.tests.integration.atcap.test_i{i}", f"test_i{i}_slow", 10.4 + 1.1 * i)
        for i in range(MAX_RERUNS)
    ]
    durations = {f"{c[0]}::{c[1]}": "0.4" for c in unit_cases + integration_cases}
    results = _results(
        tmp_path,
        ("unit.xml", _xml(unit_cases)),
        ("integration.xml", _xml(integration_cases)),
    )
    run = _run(
        results,
        {**RERUN_ON, "SLEEP_GATE_PYTEST": _stub_pytest(tmp_path, durations, calls_file=calls)},
    )
    out = _out(run)
    # Precondition first: if the corpus stopped re-running everything, the missing
    # note below would prove nothing about the trigger.
    assert len(_calls(calls)) == 2 * MAX_RERUNS, (
        f"every breach must get its re-run for 'no note' to mean anything; "
        f"saw {len(_calls(calls))}\n{out}"
    )
    assert run.returncode == 0, f"all cleared, so the run is green:\n{out}"
    notes = [ln for ln in run.stderr.splitlines() if "stay RED unverified" in ln]
    assert notes == [], (
        f"a tier AT the cap dropped nothing, so it must not claim otherwise; saw {notes!r}"
    )
    assert "only the" not in run.stderr, (
        f"no re-run was skipped here; the report must not imply one was\n{out}"
    )


def test_the_header_names_eligible_and_re_run_counts_separately(tmp_path: Path) -> None:
    """At an over-cap corpus the ENABLED line must not call the cap "one each".

    Six breaches per eligible tier, so 12 are eligible and only 2 x MAX_RERUNS
    are actually re-run. ``main``'s line already reads "6 unit breach(es) get one
    re-run each (max 5)" while it re-runs 5, so the overstatement predates ruling
    151 — but widening the tiers widens the lie to 12-while-10, and this package
    is the one that ships the sentence. A breach the cap cannot reach is NOT
    re-run; telling the reader otherwise is the same "off reads as the rule"
    shape, just wearing the leniency's clothes.

    Asserted on whole integer tokens, not substrings: at one breach the digit 1
    appears inside "6 unit, 1 integration" whatever the line means, so a
    substring check passes for a reason that does not generalise. Both counts
    must appear, and they must differ — which is only true of this corpus.
    """
    calls = tmp_path / "calls.jsonl"
    unit_cases = [
        (f"backend.tests.unit.capcount.test_u{i}", f"test_u{i}_slow", 4.4 + 0.1 * i)
        for i in range(MAX_RERUNS + 1)
    ]
    integration_cases = [
        (
            f"backend.tests.integration.capcount.test_i{i}",
            f"test_i{i}_slow",
            10.4 + 1.1 * i,
        )
        for i in range(MAX_RERUNS + 1)
    ]
    durations = {f"{c[0]}::{c[1]}": "0.4" for c in unit_cases + integration_cases}
    results = _results(
        tmp_path,
        ("unit.xml", _xml(unit_cases)),
        ("integration.xml", _xml(integration_cases)),
    )
    run = _run(
        results,
        {**RERUN_ON, "SLEEP_GATE_PYTEST": _stub_pytest(tmp_path, durations, calls_file=calls)},
    )
    out = _out(run)
    invoked = len(_calls(calls))
    eligible = 2 * (MAX_RERUNS + 1)
    header = next(line for line in out.splitlines() if "ENABLED" in line)
    tokens = {int(n) for n in re.findall(r"\d+", header)}

    assert invoked == 2 * MAX_RERUNS, (
        f"the corpus has to be over the cap in BOTH tiers for this to bite; "
        f"{invoked} re-runs\n{out}"
    )
    assert invoked in tokens, (
        f"the ENABLED line must state how many breaches it actually re-runs "
        f"({invoked}); saw: {header!r}"
    )
    assert eligible in tokens, (
        f"the line still has to say how many were eligible ({eligible}); saw: {header!r}"
    )
    assert eligible != invoked, (
        f"this corpus must separate the two counts, else the pin above is "
        f"vacuous: eligible={eligible} invoked={invoked}"
    )
    # Review finding 8: every assertion above is INTEGER-shaped, so the tier
    # WORDS in the parenthetical were free — one mutant printed "(6, 6)", another
    # "(6 tiers, 6 tiers)", both green. Per-tier framing is the whole content of
    # that clause; the counts alone do not carry it. Built from the fixture's own
    # counts, not literal digits, so a cap change cannot flip this pin into a lie
    # in the other direction.
    # Splitting on the literal rather than scanning for parens: the same line
    # carries "breach(es)" BEFORE the tier list and "(cap N per tier)" AFTER it,
    # so index("(") finds the one inside breach(es) and index(")") closes it.
    assert "breach(es)" in header, (
        f"the ENABLED line changed shape; this pin's extraction needs updating: {header!r}"
    )
    after = header.split("breach(es)", 1)[1]
    paren = after[after.index("(") + 1 : after.index(")")]
    for count, tier in ((MAX_RERUNS + 1, "unit"), (MAX_RERUNS + 1, "integration")):
        assert f"{count} {tier}" in paren, (
            f"the parenthetical must name the tier, not only its count; expected "
            f"{count} {tier} in {paren!r}"
        )


def test_the_over_budget_section_count_excludes_the_breach_that_reproduced(
    tmp_path: Path,
) -> None:
    """The section's count must be the count of ITS rows, not of all breaches.

    "OVER BUDGET, DID NOT REPRODUCE (listed, never failing): N" is the only
    place the report separates the breach that a re-run cleared from the one that
    reproduced, and the parenthetical is a promise: a number that also counts the
    reproduced breach breaks it. A one-breach corpus cannot witness that — with a
    single cleared breach, "all breaches" and "listed elsewhere" are the same
    size — so this corpus has TWO integration breaches, one clearing at 0.60 s
    and one reproducing at 13.1 s. The section must then say 1 over the one row
    it prints, while the reproduced one is counted under BREACHES instead.

    This is the shape the missing pin needs; the single-cleared pin next door
    asserts the row's CONTENT and cannot see a count that is off by the breach
    that did reproduce.
    """
    calls = tmp_path / "calls.jsonl"
    reproducer = ("backend.tests.integration.apishard.test_auth", "test_integration_auth_slow")
    results = _results(
        tmp_path,
        (
            "integration.xml",
            _xml(
                [
                    (*INTEGRATION, INTEGRATION_BREACH),
                    (*reproducer, 11.9),
                ]
            ),
        ),
    )
    durations = {f"{INTEGRATION[0]}::{INTEGRATION[1]}": INTEGRATION_CLEARANCE}
    durations[f"{reproducer[0]}::{reproducer[1]}"] = "13.1"
    run = _run(
        results,
        {**RERUN_ON, "SLEEP_GATE_PYTEST": _stub_pytest(tmp_path, durations, calls_file=calls)},
    )
    out = _out(run)
    # Precondition: the corpus must really hold one cleared and one confirmed
    # breach. If it does not, the count below is vacuous in the same way the
    # single-breach corpus was.
    assert len(_calls(calls)) == 2, f"both breaches must be re-run: {out}"
    assert run.returncode != 0, f"the 13.1 s re-run reproduced, so this run is red: {out}"

    lines = run.stdout.splitlines()
    listed = [i for i, ln in enumerate(lines) if ln.startswith("OVER BUDGET, DID NOT REPRODUCE")]
    assert len(listed) == 1, f"exactly one cleared breach should open that section: {out}"
    stated = int(lines[listed[0]].rsplit(":", 1)[1])
    body: list[str] = []
    for ln in lines[listed[0] + 1 :]:
        if ln.strip() == "":
            break
        if ln.startswith("  WARN "):
            body.append(ln)
    assert stated == len(body) == 1, (
        f"one cleared breach: the header must state 1 above the 1 row it prints. "
        f"A count of {stated} is counting the breach that DID reproduce, which is "
        f"the distinction this section's name promises\n{run.stdout}"
    )
    breach_header = next(
        (ln for ln in lines if ln.startswith("BREACHES (over the hard budget)")), ""
    )
    assert breach_header.rstrip().endswith(": 1"), (
        f"and the reproduced breach belongs under BREACHES, not here: "
        f"{breach_header!r}\n{run.stdout}"
    )


def test_tiers_outside_the_clause_are_still_never_re_run(tmp_path: Path) -> None:
    """e2e and slow stay RED-unverified with no subprocess spawned.

    The amendment names only the integration tier, and the reasons for the other
    two survive it. The audit job downloads Playwright's junit too (its
    ``playwright-test-results-*`` download step), so e2e ids
    really are in the corpus it reads — the filter has to be
    ``("unit", "integration")`` and NOT "everything that is not unit", or every
    e2e failure spawns a subprocess in a job with no browser and no ``npm ci``.
    The ``slow`` tier is measured-slow by census, so a re-run there buys a
    60 s-class sleep, not a flake verdict.
    """
    calls = tmp_path / "calls.jsonl"
    results = _results(
        tmp_path,
        ("e2e.xml", _xml([("specs/edge_case_matrix.spec.ts", "test_slow_spec", 23.1)])),
        (
            "slow.xml",
            _xml(
                [
                    (
                        "backend.tests.unit.perf.test_fast_path",
                        "test_fast_path_high_priority_detection",
                        71.0,
                    )
                ]
            ),
        ),
    )
    run = _run(
        results,
        {**RERUN_ON, "SLEEP_GATE_PYTEST": _stub_pytest(tmp_path, {}, calls_file=calls)},
    )
    out = _out(run)
    assert run.returncode != 0, f"a 23.1 s e2e and a 71 s slow breach are both RED\n{out}"
    assert _calls(calls) == [], (
        "e2e and slow are outside the tiers the re-run covers; an attempt would "
        f"be a doomed subprocess, not a measurement: {_calls(calls)}"
    )


def test_the_enabled_header_counts_what_the_gate_actually_re_runs(
    tmp_path: Path,
) -> None:
    """The header must not report a unit-only count once other tiers qualify.

    One integration breach, nothing else. Today the line reads "0 unit
    breach(es) get one re-run each" while the gate is about to re-run one (after
    the fix) — a report that denies the regime it is running under, which is the
    WP0.5 "off reads as the rule" shape this block has warned about since ruling
    122. Asserted against the invocations rather than a phrasing, so the pin
    cannot be satisfied by a prettier sentence that still miscounts.
    """
    calls = tmp_path / "calls.jsonl"
    results = _results(tmp_path, ("integration.xml", _xml([(*INTEGRATION, INTEGRATION_BREACH)])))
    run = _run(
        results,
        {
            **RERUN_ON,
            "SLEEP_GATE_PYTEST": _stub_pytest(
                tmp_path, {INTEGRATION_ID: INTEGRATION_CLEARANCE}, calls_file=calls
            ),
        },
    )
    out = _out(run)
    invoked = _calls(calls)
    assert len(invoked) == 1, (
        f"the tier has to be re-run at all before the header can count it\n{out}"
    )
    header = next(line for line in out.splitlines() if "ENABLED" in line)
    assert str(len(invoked)) in header, (
        f"the ENABLED line must state the count it is honouring; saw: {header!r}"
    )
    assert "0 unit breach" not in header, (
        f"a header that says zero while re-running something is the shape this "
        f"file exists to prevent; saw: {header!r}"
    )
