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
victim set rotates between same-code runs (12/13/10 ids across three green
main runs; up to 20 ids straddle the line) — a hard threshold inside the
runner's noise band is a lottery, not a signal, and with the file gone there is
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
import sys
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


def write_step_summary(warns: list[tuple[float, str]], breaches: list[tuple[float, str]]) -> None:
    """Append the WARN section to ``$GITHUB_STEP_SUMMARY``; never fail on it.

    Ruling 93's "listed in the job summary" is a destination: the owner reads
    the numbers on the run page, not in a scrollback log. Breached unit tests
    appear here too — the failing run is exactly when the distribution matters
    most. An unwritable path prints a stderr note and returns: this function
    changing anyone's verdict would defeat the tier it serves.
    """
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    if not summary_path or not (warns or breaches):
        return
    lines = [
        "## Real-sleep duration budget (ruling 93)",
        "",
        f"Unit tests over the {get_warn_budget()}s WARN threshold "
        "(warn never fails the run; hard budgets are in the job log):",
        "",
    ]
    for duration, test_id in warns:
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
    print("REAL-SLEEP DURATION BUDGET GATE (rulings 74 + 93)")
    print("=" * 70)
    print(
        f"Budgets: unit={budgets['unit']}s, integration={budgets['integration']}s, "
        f"e2e={budgets['e2e']}s, slow={budgets['slow']}s, warn(unit)={warn_budget}s"
    )
    print(f"Corpus: {xml_count} XML file(s), {len(worst)} test(s) with a recorded duration")
    print("No previous-run downgrade and no exemption file: every breach is RED.")
    print()

    if warns:
        print(f"WARN (unit tests over {warn_budget}s — listed, never failing): {len(warns)}")
        print("-" * 40)
        for duration, test_id in warns:
            print(f"  WARN {duration:.2f}s (warn budget: {warn_budget}s)")
            print(f"    {test_id}")
        print()

    # Written on RED runs too — the summary's value peaks exactly when the
    # gate has just refused a merge.
    write_step_summary(warns, [(d, t) for d, t, _, _ in breaches])

    if breaches:
        print(f"BREACHES (over the hard budget): {len(breaches)}")
        print("-" * 40)
        for duration, test_id, category, budget in breaches:
            print(f"  BREACH {duration:.2f}s (budget: {budget}s) [{category}]")
            print(f"    {test_id}")
        print()
        print("=" * 70)
        print(
            f"RESULT: FAIL - {len(breaches)} test(s) over their real-sleep budget. A "
            "seconds-scale unit test is a real sleep: give it a fake/injected clock "
            "or make it genuinely faster. There is no file to add it to."
        )
        return 1

    print("RESULT: PASS - no test over its real-sleep budget")
    return 0


if __name__ == "__main__":
    sys.exit(main())
