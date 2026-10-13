#!/usr/bin/env python3
"""Fail any test whose call time exceeds a real-sleep budget (owner rulings 74 + 93).

**The rule (ruling 93, 2026-10-11, amending ruling 74).** Verbatim: "Hard fail:
any unit test over **4.0 s**, with **no** 'healthy in the previous main run'
downgrade. That missing downgrade is what this gate adds over the Test
Performance Audit. Warn: any unit test over **1.5 s** is listed in the job
summary; it never fails the run. **No baseline file.**"

What this is NOT, and why it exists beside the audit rather than inside it:
``scripts/audit-test-durations.py`` limits unit tests at 4.0 s and, since WP1.3,
downgrades a mild breach on a test that was healthy in its own previous run to a
warning. That downgrade is the right answer to a measured problem (one timing
sample on a contended shared runner reddened 15/45 PR runs on identical code)
and the wrong answer to the question this gate asks. A hand-written ``sleep(1.8)``
is not noise — it is the same value every run — so forgiving a duration by
history forgives exactly the thing being hunted. This gate therefore reads no
previous run and no exemption file of any kind: one corpus, one pass.

Budgets are the audit's OWN CI-set limits, and the gate's whole content is the
missing downgrade, not a stricter line:

    hard  unit         4.0 s   (= the audit's UNIT_TEST_THRESHOLD)
    hard  integration 10.0 s   (= its INTEGRATION_TEST_THRESHOLD)
    hard  e2e         10.0 s   (= its E2E_TEST_THRESHOLD)
    hard  slow        60.0 s   (= its SLOW_TEST_THRESHOLD, kept — see below)
    warn  unit         1.5 s   (listed in the job summary, never fails)

Why the hard line moved from ruling 74's 1.5 s to 4.0 s: the measured over-1.5
victim set rotates between same-code runs — over the three shipping green-main
corpora it is 31/22/17 ids with an intersection of only 10, and up to 20 ids
newly cross the line in one direction between two runs (29 in symmetric
difference; 12/13/10 NEWCOMERS per PR run was the first-flight baseline
figure, a different measurement) — so a hard threshold inside the runner's
noise band is a lottery, not a signal, and with the file gone there is
nothing to hold the rotation. 4.0 s is where all three green corpora flip ZERO
ids (measured max unit duration 6.01 s, and that one is tracked-slow). The 1.5 s
line keeps its information value exactly where ruling 93 put it: loudly listed,
never red. The corpus's p99.9 sits at 1.90 s, so the WARN band is precisely the
"something slept" neighborhood.

The ``slow`` tier keeps its 60 s cap (recorded interpretation for the reviewer):
ruling 74 deliberately judged tracked-slow at the unit budget because its
exemptions lived in one shrink-only file. That file is now retired, and the
audit's tracked-slow list IS a human-adjudication channel — an entry needs a
measured corpus breach AND a ``tpa_slow_list`` census line — so the bucket the
classifier does not call unit keeps the audit's own cap. Without it, the rtsp
socket-timeout test (measured 6.01 s on main) is a permanent false-red nobody
can merge against, and "permanent red" silences a gate faster than any flag.

Usage:
    python scripts/check-test-duration-budget.py <results-dir>

Environment variables (the CI step is the single place the owner's numbers are
written; same shape as the audit's ``UNIT_TEST_THRESHOLD``):
    SLEEP_GATE_UNIT_BUDGET         unit hard budget, seconds (default 4.0)
    SLEEP_GATE_INTEGRATION_BUDGET  integration hard budget, seconds (default 10.0)
    SLEEP_GATE_E2E_BUDGET          e2e hard budget, seconds (default 10.0)
    SLEEP_GATE_SLOW_BUDGET         tracked-slow cap, seconds (default 60.0)
    SLEEP_GATE_WARN_BUDGET         unit warn threshold, seconds (default 1.5)

The WARN list is also appended to ``$GITHUB_STEP_SUMMARY`` when set, because
"listed in the job summary" names the destination, not a metaphor. A summary
that cannot be written (odd permissions, a path that is a directory) degrades to
a stderr note — the WARN tier exists to never change the verdict, and an
I/O error must not become one.

Tier classification is the AUDIT'S OWN ``categorize_test``, imported rather than
reimplemented: the gate and the audit must never disagree about what tier a test
is. (This lane's first pass path-guessed tiers and over-counted the subject set
-- the classifier's number is the one that re-measures: 46 unit ids over 1.5 s
in the three shipping corpora, because ``categorize_test`` routes the
299-collected-test ``test_gpu_monitor_batch28_*`` cluster to ``integration`` on
its "gpu" substring and the five over-1.5 s tracked-slow members to ``slow``.
The naive guess's total is deliberately NOT quoted: self-review F4 showed it
depends on the guesser's own heuristic -- two re-implementations of "path only"
got two different totals off the same corpora.)

Fail-closed on zero evidence, copied reasoning from the audit's WP0.5 rule: both
artifact downloads in the job this runs in carry ``continue-on-error: true``, so
a broken upload looks exactly like an empty corpus — a gate that exits 0 here is
switched off by the thing it should catch. The same rule covers the corrupt
shape: XML files that PARSE to no durations at all (truncated upload, writer
killed mid-flush) fail too, because "N files, 0 durations" over-budgets nothing
and would otherwise PASS vacuously on data it never read.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import defusedxml.ElementTree as ET

REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIT_SCRIPT = Path(__file__).resolve().parent / "audit-test-durations.py"

# tier -> default budget; values are the audit's own CI-set thresholds.
DEFAULT_UNIT_BUDGET = 4.0
DEFAULT_INTEGRATION_BUDGET = 10.0
DEFAULT_E2E_BUDGET = 10.0
DEFAULT_SLOW_BUDGET = 60.0
DEFAULT_WARN_BUDGET = 1.5


def load_categorize() -> Any:
    """The audit's tier classifier, by path (its filename has a dash).

    Import is safe: audit-test-durations.py runs nothing at module scope beyond
    definitions — ``main()`` sits behind an ``if __name__ == "__main__"`` guard
    at its end — so this costs no work and triggers no network or file access.
    """
    spec = importlib.util.spec_from_file_location("_r93_audit_classifier", AUDIT_SCRIPT)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load the tier classifier from {AUDIT_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.categorize_test


categorize_test = load_categorize()


def get_budgets() -> dict[str, float]:
    """Budget per tier, env-overridable. Unknown tiers get the unit budget."""
    unit = float(os.environ.get("SLEEP_GATE_UNIT_BUDGET", str(DEFAULT_UNIT_BUDGET)))
    return {
        "unit": unit,
        "integration": float(
            os.environ.get("SLEEP_GATE_INTEGRATION_BUDGET", str(DEFAULT_INTEGRATION_BUDGET))
        ),
        "e2e": float(os.environ.get("SLEEP_GATE_E2E_BUDGET", str(DEFAULT_E2E_BUDGET))),
        "slow": float(os.environ.get("SLEEP_GATE_SLOW_BUDGET", str(DEFAULT_SLOW_BUDGET))),
    }


def get_warn_budget() -> float:
    """The unit-tier WARN threshold (ruling 93: 1.5 s, listed, never fails)."""
    return float(os.environ.get("SLEEP_GATE_WARN_BUDGET", str(DEFAULT_WARN_BUDGET)))


def budget_for(category: str, budgets: dict[str, float]) -> float:
    """The budget that applies to one tier.

    Tracked tiers get their own line; the audit's four are all pinned above.
    An unknown future category falls to the unit budget — the strictest
    sensible default, so a new tier in the classifier becomes a loud review
    conversation here rather than a silent exemption.
    """
    return budgets.get(category, budgets["unit"])


# ---------------------------------------------------------------------------
# UR-125 AS AMENDED: a unit-tier breach must REPRODUCE before it goes red.
#
# Verbatim: "The real-sleep gate fails a unit test over 4.0 s only when the
# breach reproduces: the gate re-runs that one test once, in the same job, and
# the run is red only if the re-run also breaches; a test that passes on its
# re-run is listed as a warning with both timings."
#
# Three properties the rest of this block exists to keep true, each with a pin:
# * the re-run is OFF unless the CI step turns it on. A junit corpus describes
#   the machine that wrote it, so replaying one anywhere else compares two
#   boxes and could CLEAR a genuine breach; the audit job is the one place the
#   checkout IS the tree that produced the junit. Unset, this script is ruling
#   93 byte for byte — and the knob names no test, widens no budget and reads
#   no previous run, so it is not the exemption channel ruling 93 deleted.
# * an UNVERIFIED re-run stays RED. "Could not check" is not "passed", the same
#   WP0.5 doctrine the corpus-level checks apply to a missing corpus.
# * the report says which of its three states it is in (confirmed / did not
#   reproduce / not enabled), so "off" never reads as "the rule".
# ---------------------------------------------------------------------------

# Re-runs are one per breaching test; the cap bounds what a pathological corpus
# can cost the job (5 sleeps worst case) rather than letting a red shard spawn
# hundreds. Breaches past the cap stay RED — the cap can only ever be strict.
MAX_RERUNS = 5

# The re-run's own per-test ceiling. Inherited ``addopts`` carries
# ``timeout = 5``, which is UNDER the 4.0 s budget it is supposed to adjudicate:
# a 4.5 s test would be killed by pytest-timeout at 5 s and the plugin's
# ceiling, not the owner's number, would decide the verdict. Generous on
# purpose — the budget still decides; this only decides "did not finish".
DEFAULT_RERUN_TIMEOUT = 120.0


def rerun_enabled() -> bool:
    """Is the re-run on? Only the audit job's step sets this (see ci.yml)."""
    return os.environ.get("SLEEP_GATE_RERUN", "").strip() not in ("", "0", "false", "no")


def rerun_command() -> list[str]:
    """The argv prefix used to re-run one test.

    Default is ``<this interpreter> -m pytest`` — not a bare ``pytest`` that
    could resolve to something off PATH. The gate is started by the same
    interpreter the job installed the dev extra for, so module invocation is
    the one spelling guaranteed to reach the pytest that ran the corpus.
    ``SLEEP_GATE_PYTEST`` replaces the prefix (tests point it at a stub).
    """
    override = os.environ.get("SLEEP_GATE_PYTEST", "").strip()
    if override:
        return shlex.split(override)
    return [sys.executable, "-m", "pytest"]


def pytest_target_for(test_id: str) -> str:
    """junit's ``dotted.classname::name`` → pytest's ``path/to/file.py::…``.

    The inversion has to get the module boundary right, not just the dots: a
    class member's junit classname is ``pkg.mod.TestKlass`` with ``name`` a
    method, and pytest wants ``pkg/mod.py::TestKlass::method``. Getting this
    subtly wrong is the nastiest failure this block can have — every re-run
    selects zero tests, the gate reports "could not verify" forever, and it
    looks like a rigorous gate that happens to see no flakes.

    Module segments are the leading ones that are not capitalised: PEP-8 module
    names are lowercase and a class is the first capitalised segment, which is
    also how the repo's own ids arrive from junit. No filesystem probe: the
    corpus may describe files this checkout no longer has, and a probe that
    missed would silently change the target shape.
    """
    classname, _, name = test_id.partition("::")
    parts = [p for p in classname.split(".") if p]
    cut = next((i for i, p in enumerate(parts) if p[:1].isupper()), len(parts))
    module = "/".join(parts[:cut]) + ".py" if cut else classname.replace(".", "/") + ".py"
    return "::".join([module, *parts[cut:], name])


def _repro_timeout() -> float:
    return float(os.environ.get("SLEEP_GATE_RERUN_TIMEOUT", str(DEFAULT_RERUN_TIMEOUT)))


def _rerun_duration(target: str) -> tuple[float | None, int]:
    """Re-run one test once; return ``(seconds or None, pytest exit code)``.

    The argv is deliberately not the job's: ``-o addopts=`` clears
    ``pyproject.toml``'s ``-n 8 --dist=worksteal`` (re-measuring a sleep under
    8-way contention would CONFIRM a breach using the very starvation the
    amendment forgives) and its ``timeout = 5``, which this replaces with an
    explicit ``--timeout``. ``cwd`` is the repo root because the target is a
    repo-relative path.

    Returns ``None`` for the duration whenever there is no usable number — no
    junit, an unparseable one, or a zero-duration testcase, which junit emits
    for a skip and which the corpus pass already refuses to read as "fast".
    """
    argv = [
        *rerun_command(),
        "-o",
        "addopts=",
        "-p",
        "no:randomly",
        f"--timeout={_repro_timeout():g}",
        "--junit-xml=@TEMP@",
        target,
    ]
    with tempfile.TemporaryDirectory(prefix="sleep-gate-repro-") as tmpdir:
        xml_path = Path(tmpdir) / "repro.xml"
        argv[argv.index("--junit-xml=@TEMP@")] = f"--junit-xml={xml_path}"
        try:
            # Fixed argv list, no shell, cwd pinned to REPO_ROOT; S603 is
            # ignored for scripts/ in pyproject.toml on exactly that rationale.
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                check=False,
                cwd=REPO_ROOT,
            )
        except OSError as exc:
            # The prefix itself will not start (bad SLEEP_GATE_PYTEST, no
            # interpreter). That is "not verified", not "passed".
            print(f"  (re-run could not start: {exc})", file=sys.stderr)
            return None, 127
        # returncode is carried out with the duration and decides the state in
        # reproduce(): 0 = passed, 1 = failed, 5 = nothing collected. Only a
        # clean 0 can exonerate anything (UR-125: "passes on its re-run").
        if not xml_path.is_file():
            return None, proc.returncode
        try:
            root = ET.parse(xml_path).getroot()
        except ET.ParseError:
            return None, proc.returncode
        durations: list[float] = []
        suites = root.findall("testsuite") if root.tag == "testsuites" else [root]
        for suite in suites:
            for case in suite.findall("testcase"):
                try:
                    d = float(case.get("time", "0"))
                except ValueError:
                    continue
                if d > 0:
                    durations.append(d)
        if not durations:
            return None, proc.returncode
        return max(durations), proc.returncode


def reproduce(
    breaches: list[tuple[float, str, str, float]],
) -> dict[str, tuple[str, float | None, int]]:
    """One re-run per unit-tier breach: ``test_id -> (state, seconds, exit)``.

    ``state`` is ``confirmed`` (re-ran and breached again), ``cleared`` (passed
    under budget), or ``unverified`` (nothing about this run says the duration
    was a fluke — including "it failed fast", which is a caught test, not an
    exonerated one). Non-unit tiers are not returned: the amendment speaks
    about unit tests, and the audit job has no browser and no ``npm ci``, so an
    e2e re-run there is a doomed subprocess, not a measurement.
    """
    states: dict[str, tuple[str, float | None, int]] = {}
    if not rerun_enabled():
        return states
    eligible = [b for b in breaches if b[2] == "unit"]
    if len(eligible) > MAX_RERUNS:
        print(
            f"  note: {len(eligible)} unit breaches, only the {MAX_RERUNS} slowest get a "
            "re-run; the rest stay RED unverified",
            file=sys.stderr,
        )
    for _, test_id, _category, budget in eligible[:MAX_RERUNS]:
        seconds, code = _rerun_duration(pytest_target_for(test_id))
        if seconds is None:
            states[test_id] = ("unverified", None, code)
        elif code != 0:
            states[test_id] = ("unverified", seconds, code)
        elif seconds > budget:
            states[test_id] = ("confirmed", seconds, code)
        else:
            states[test_id] = ("cleared", seconds, code)
    return states


def worst_durations(
    results_dir: Path,
) -> tuple[dict[str, tuple[float, str]], int, int]:
    """``test id -> (worst duration, tier)`` over every XML in the corpus.

    Returns ``(worst, xml_file_count, timed_testcase_count)``. The third count
    is taken BEFORE the benchmark tier is dropped, so the caller can tell "the
    corpus is corrupt/partial" (files, but no testcase has a usable duration)
    from "the corpus is legitimately all-benchmark" (durations present, tier
    filtered out).

    Duplicates take the MAX: junit emits one ``<testcase>`` per invocation, so a
    parameterised id appears several times and a shard retry can repeat an id
    outright. The first or the mean would let a test that breached once look
    cheap.

    Zero-duration testcases are skipped exactly as the audit skips them — that is
    a skipped test, not a fast one.
    """
    worst: dict[str, tuple[float, str]] = {}
    xml_count = 0
    timed_cases = 0
    for xml_file in sorted(results_dir.glob("**/*.xml")):
        xml_count += 1
        try:
            root = ET.parse(xml_file).getroot()
        except ET.ParseError as exc:
            print(f"Warning: could not parse {xml_file}: {exc}", file=sys.stderr)
            continue
        suites = root.findall("testsuite") if root.tag == "testsuites" else [root]
        for suite in suites:
            for case in suite.findall("testcase"):
                classname = case.get("classname", "")
                name = case.get("name", "")
                try:
                    duration = float(case.get("time", "0"))
                except ValueError:
                    duration = 0.0
                if duration <= 0:
                    continue
                timed_cases += 1  # before the benchmark drop — see docstring
                category = categorize_test(classname, name, str(xml_file))
                if category == "benchmark":
                    continue  # measured latency on purpose; the audit drops these
                test_id = f"{classname}::{name}"
                current = worst.get(test_id)
                if current is None or duration > current[0]:
                    worst[test_id] = (duration, category)
    return worst, xml_count, timed_cases


def write_step_summary(
    warns: list[tuple[float, str]],
    breaches: list[tuple[float, str]],
    cleared: dict[str, tuple[str, float | None, int]] | None = None,
) -> None:
    """Append the WARN section to ``$GITHUB_STEP_SUMMARY``; never fail on it.

    Ruling 93's "listed in the job summary" is a destination: the owner reads
    the numbers on the run page, not in a scrollback log. Breached unit tests
    appear here too — the failing run is exactly when the distribution matters
    most. An unwritable path prints a stderr note and returns: this function
    changing anyone's verdict would defeat the tier it serves.

    ``cleared`` is the UR-125 re-run result for breaches that did not
    reproduce. Those ids are already in WARNS (a 4.5 s unit test is over the
    1.5 s warn threshold by definition), so they get ONE row here rather than a
    second section — and that row carries the corpus timing AND the re-run
    timing, because a row that shows only the flattering number deletes the
    event the owner declined to forgive.
    """
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    if not summary_path or not (warns or breaches):
        return
    cleared = cleared or {}
    lines = [
        "## Real-sleep duration budget (ruling 93, UR-125 as amended)",
        "",
        f"Unit tests over the {get_warn_budget()}s WARN threshold "
        "(warn never fails the run; hard budgets are in the job log):",
        "",
    ]
    for duration, test_id in warns:
        if test_id in cleared:
            replay = cleared[test_id][1]
            tail = f"{replay:.2f}s" if replay is not None else "no timing"
            lines.append(
                f"- `{test_id}` — {duration:.2f}s over budget, re-ran {tail} "
                "(did not reproduce; listed, not failed)"
            )
            continue
        lines.append(f"- `{test_id}` — {duration:.2f}s")
    if breaches:
        lines += ["", "Hard-budget breaches (this run is RED):", ""]
        lines += [f"- `{test_id}` — {duration:.2f}s" for duration, test_id in breaches]
    lines.append("")
    try:
        # GITHUB_STEP_SUMMARY is set by the Actions runner, never derived from
        # corpus data — same shape as scripts/analyze-flaky-tests.py.
        with open(summary_path, "a", encoding="utf-8") as handle:  # nosemgrep: path-traversal-open
            handle.write("\n".join(lines))
    except OSError as exc:
        print(f"Warning: could not write $GITHUB_STEP_SUMMARY: {exc}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail tests over their real-sleep budget (rulings 74 + 93).",
    )
    parser.add_argument("results_dir", help="directory of junit XMLs (scanned recursively)")
    args = parser.parse_args(argv)

    results_dir = Path(args.results_dir)
    if not results_dir.is_dir():
        print(
            f"Error: results directory not found: {results_dir} — the gate ran with no "
            "test data; failing rather than passing vacuously.",
            file=sys.stderr,
        )
        return 1

    worst, xml_count, timed_cases = worst_durations(results_dir)
    if xml_count == 0:
        # WP0.5's rule, inherited: this job's artifact downloads are
        # continue-on-error, so an empty corpus is what a broken upload looks
        # like. Exit 0 here would be a gate silently switched off.
        print(
            f"Error: no JUnit XML found under {results_dir} — the gate ran with no test "
            "data; failing rather than passing vacuously.",
            file=sys.stderr,
        )
        return 1
    if xml_count and timed_cases == 0:
        # The same WP0.5 reasoning one level deeper: xml_count counts FILES, and
        # a file contributes to it before it parses (and even when every
        # <testcase> inside it carries no usable time= — a truncated upload, a
        # writer killed mid-flush). Zero timed testcases over N files is that
        # broken-upload shape with the files present; over-budget stays empty
        # and the gate would PASS vacuously on data it never read. The predicate
        # is timed_cases, NOT "worst is empty": a corpus of only benchmark tests
        # has durations and legitimately an empty subject set (the tier is
        # excluded by design), and must stay green.
        print(
            f"Error: {xml_count} JUnit XML file(s) under {results_dir} yielded 0 "
            "test(s) with a recorded duration — corrupt or partial junit, not an "
            "empty corpus; failing rather than passing vacuously.",
            file=sys.stderr,
        )
        return 1

    budgets = get_budgets()
    warn_budget = get_warn_budget()

    breaches = sorted(
        (
            (duration, test_id, category, budget_for(category, budgets))
            for test_id, (duration, category) in worst.items()
            if duration > budget_for(category, budgets)
        ),
        key=lambda b: -b[0],
    )
    # The WARN list is the unit tier only — ruling 93 says "any unit test over
    # 1.5 s". Other tiers keep their own limits and their own summary noise;
    # listing a 2.6 s banner spec (legal at its 10.0 s limit) as "slow" would
    # train everyone to skim the list, and the tracked-slow census members
    # would live in it permanently.
    warns = sorted(
        (
            (duration, test_id)
            for test_id, (duration, category) in worst.items()
            if category == "unit" and duration > warn_budget
        ),
        key=lambda w: -w[0],
    )

    print("=" * 70)
    print("REAL-SLEEP DURATION BUDGET GATE (rulings 74 + 93, UR-125 as amended)")
    print("=" * 70)
    print(
        f"Budgets: unit={budgets['unit']}s, integration={budgets['integration']}s, "
        f"e2e={budgets['e2e']}s, slow={budgets['slow']}s, warn(unit)={warn_budget}s"
    )
    print(f"Corpus: {xml_count} XML file(s), {len(worst)} test(s) with a recorded duration")

    # UR-125 as amended: a unit-tier breach has to REPRODUCE before it reddens
    # the run. One re-run per breaching id, in this job, on this checkout.
    # Everything below is decided by what those re-runs said, so the header
    # states which regime this run was under rather than asserting ruling 93's
    # "every breach is RED" unconditionally -- that sentence is exactly what the
    # amendment changed, and a report that denies it while downgrading is the
    # WP0.5 "off reads as the rule" shape.
    states = reproduce(breaches)
    cleared = {t: s for t, s in states.items() if s[0] == "cleared"}
    confirmed = {t: s for t, s in states.items() if s[0] == "confirmed"}
    unverified = {t: s for t, s in states.items() if s[0] == "unverified"}
    unit_breaches = [b for b in breaches if b[2] == "unit"]

    if not rerun_enabled():
        if unit_breaches:
            print(
                "Re-run of a breach: NOT ENABLED (SLEEP_GATE_RERUN unset), so every "
                "breach below is unverified and ruling 93's verdict stands: RED."
            )
        else:
            print("Re-run of a breach: not enabled (no unit breach to reproduce anyway).")
    else:
        print(
            f"Re-run of a breach: ENABLED — {len(unit_breaches)} unit breach(es) get one "
            f"re-run each (max {MAX_RERUNS}); only a reproduced breach is RED."
        )
    print("No previous-run downgrade and no exemption file.")
    print()

    if warns:
        print(f"WARN (unit tests over {warn_budget}s — listed, never failing): {len(warns)}")
        print("-" * 40)
        for duration, test_id in warns:
            cleared_here = cleared.get(test_id)
            if cleared_here:
                # Both timings on the ONE line that names the test. Showing only
                # the flattering 0.40 s would erase the 4.5 s event from the
                # record, which is the downgrade the owner did not grant.
                print(
                    f"  WARN {test_id} — corpus {duration:.2f}s, re-ran "
                    f"{cleared_here[1]:.2f}s (over budget, did not reproduce)"
                )
                continue
            print(f"  WARN {duration:.2f}s (warn budget: {warn_budget}s)")
            print(f"    {test_id}")
        print()

    # A breach that cleared is no longer a breach; it is the warning above.
    red = [b for b in breaches if b[1] not in cleared]

    # Written on RED runs too — the summary's value peaks exactly when the
    # gate has just refused a merge.
    write_step_summary(warns, [(d, t) for d, t, _, _ in red], cleared)

    if red:
        print(f"BREACHES (over the hard budget): {len(red)}")
        print("-" * 40)
        for duration, test_id, category, budget in red:
            verdict = f"  BREACH {duration:.2f}s (budget: {budget}s) [{category}]"
            again = confirmed.get(test_id)
            if again:
                verdict += f" — re-ran {again[1]:.2f}s and BREACHED AGAIN"
            elif test_id in unverified:
                code = unverified[test_id][2]
                replay = unverified[test_id][1]
                timing = f"{replay:.2f}s, " if replay is not None else ""
                verdict += f" — re-run not verified ({timing}pytest exit {code})"
            print(verdict)
            print(f"    {test_id}")
        print()
        print("=" * 70)
        notes = ""
        if unverified:
            notes = (
                f" {len(unverified)} of them could not be verified by a re-run, which is "
                "NOT a pass (UR-125 exonerates only a test that passes on its re-run)."
            )
        print(
            f"RESULT: FAIL - {len(red)} test(s) over their real-sleep budget."
            f"{notes} A seconds-scale unit test is a real sleep: give it a "
            "fake/injected clock "
            "or make it genuinely faster. There is no file to add it to."
        )
        return 1

    if cleared:
        # "no test over its budget" is false here: one WAS over, and a re-run
        # is what let it through. Saying so keeps the green honest — the
        # downgrade is the point of the amendment, not a fact to hide.
        print(
            f"RESULT: PASS - nothing over budget reproduced on its re-run. "
            f"{len(cleared)} unit test(s) were over budget in the corpus and cleared a "
            "re-run; they are listed as warnings above."
        )
        return 0
    print("RESULT: PASS - no test over its real-sleep budget")
    return 0


if __name__ == "__main__":
    sys.exit(main())
