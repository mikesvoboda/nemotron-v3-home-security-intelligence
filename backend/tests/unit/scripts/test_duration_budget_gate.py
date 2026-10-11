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
   rotates (measured: 12/13/10 ids across same-code runs, one shared); with
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
test is. (This lane's measurement pass path-guessed tiers first and counted 63
over-budget unit ids where the classifier counts 46 — it routes the
``test_gpu_monitor_batch28_*`` cluster to ``integration`` on its "gpu"
substring. That 17-id disagreement is why the reuse is itself a tested
assertion.)

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
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPO_ROOT / "scripts" / "check-test-duration-budget.py"
BASELINE_FILE = REPO_ROOT / "scripts" / "duration-budget-baseline.json"

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
    reddened innocent tests; the measured over-1.5 set rotated 12/13/10 ids
    between same-code runs, which is what ruling 93 fixed.
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
    """The classifier, not a path guess, decides the tier — 17 ids of proof.

    This lane's measurement pass path-guessed tiers and reported 63 over-budget
    unit ids where the classifier reports 46, because ``categorize_test`` sends
    any test with "gpu" in it to ``integration`` on its substring pattern. If
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
        "path-guessing gate would call this unit and red it at 4.0 — the 63-vs-46 "
        f"disagreement this assertion exists to prevent\n{_out(run)}"
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
    only place those ids could live: the measured tracked-slow members
    (``test_rtsp_test_service::test_connection_timeout`` 6.01 s — a real
    socket timeout; the job_progress pair ~15.3 s; the error_handler
    ~16.5 s) would be a PERMANENT false-red on main at a 4.0 s unit budget
    with no exemption channel. The audit's ``SLOW_TEST_PATTERNS`` list is
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
