#!/usr/bin/env python3
"""Fail any test whose call time exceeds a real-sleep budget (owner ruling 74).

**The rule.** "Real sleeps in unit tests are caught by a post-run gate script
over the per-test durations CI already records. It runs after the unit shards,
like the Test Performance Audit, and fails any unit test whose call time
exceeds a budget well under the audit's 4.0 s limit, with no 'healthy in the
previous run' downgrade. … Tests over the budget today are listed in the PR and
either fixed in it or held in a baseline file that may only shrink."

What this is NOT, and why it exists beside the audit rather than inside it:
``scripts/audit-test-durations.py`` limits unit tests at 4.0 s and, since WP1.3,
downgrades a mild breach on a test that was healthy in its own previous run to a
warning. That downgrade is the right answer to a measured problem (one timing
sample on a contended shared runner reddened 15/45 PR runs on identical code)
and the wrong answer to the question ruling 74 asks. A hand-written
``sleep(1.8)`` is not noise — it is the same value every run — so forgiving a
duration by history forgives exactly the thing being hunted. This gate therefore
reads no previous run at all: one corpus, one pass, one shrink-only exemption
file. It is the loud version of the band the audit only *warns* in.

Budgets (MEASURE/DECIDE in the package PR; the ratio to each audit limit is the
point, not the absolute number):

    unit         1.5 s   (audit limit 4.0 s — 0.375x)
    integration  6.0 s   (audit limit 10.0 s — 0.6x)
    e2e          5.0 s   (audit limit 10.0 s — 0.5x)

1.5 s is ~2.8x the measured unit p99 (0.53 s) and ~77% of the measured p99.9
(1.95 s): the distribution's body is milliseconds, so anything at seconds is the
anomaly class, and the redis-backoff case this gate was ruled over (3.85 s,
4.11/4.31 s on main) breached 4.0 only intermittently — a budget near the
jitter boundary is the failure mode, not the tolerance.

Usage:
    python scripts/check-test-duration-budget.py <results-dir>
        [--baseline FILE] [--update]

Environment variables (the CI step is the single place the owner's numbers are
written; same shape as the audit's ``UNIT_TEST_THRESHOLD``):
    SLEEP_GATE_UNIT_BUDGET         unit budget, seconds (default 1.5)
    SLEEP_GATE_INTEGRATION_BUDGET  integration budget, seconds (default 6.0)
    SLEEP_GATE_E2E_BUDGET          e2e budget, seconds (default 5.0)
    SLEEP_GATE_BASELINE            exemption file (default: this script's
                                   duration-budget-baseline.json)
    SLEEP_GATE_UPDATE              "1" = shrink the baseline in place

Tier classification is the AUDIT'S OWN ``categorize_test``, imported rather than
reimplemented: the gate and the audit must never disagree about what tier a test
is, or the baseline the PR records is not the baseline the gate reads. (Measured
on this lane's own first pass: path-guessing the tiers counted 63 over-budget
unit ids where the classifier counts 46 — it routes the ``test_gpu_monitor_
batch28_*`` cluster to ``integration`` on its "gpu" substring, and the tracked-
slow pair to ``slow``.) The audit's ``slow`` bucket gets NO 60 s cap here and
falls to the unit budget: ruling 74 wants its exemptions in ONE shrink-only
file, not spread across a second allowlist that no PR has to argue with.

Fail-closed on zero XML, copied reasoning from the audit's WP0.5 rule: both
artifact downloads in the job this runs in carry ``continue-on-error: true``, so
a broken upload looks exactly like an empty corpus — a gate that exits 0 here is
switched off by the thing it should catch.

The baseline may only SHRINK. ``--update`` writes the ids that are still over
budget and REFUSES, loudly and without writing, any id not already in the file —
the same adjudication rule as ``scripts/ratchet-check.py``, whose ``--update``
"refuses to raise … the adjudication must be a human's diff". A new slow test is
fixed or it is a human's deliberate diff; it is never added by the tool that
found it.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

import defusedxml.ElementTree as ET

REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIT_SCRIPT = Path(__file__).resolve().parent / "audit-test-durations.py"
BASELINE_DEFAULT = Path(__file__).resolve().parent / "duration-budget-baseline.json"

# tier -> default budget. "slow" is deliberately absent: the audit's tracked-slow
# bucket falls to the unit budget via DEFAULT_BUDGETS.get(category, unit).
DEFAULT_UNIT_BUDGET = 1.5
DEFAULT_INTEGRATION_BUDGET = 6.0
DEFAULT_E2E_BUDGET = 5.0


def load_categorize() -> Any:
    """The audit's tier classifier, by path (its filename has a dash).

    Import is safe: audit-test-durations.py runs nothing at module scope beyond
    definitions — ``main()`` sits behind an ``if __name__ == "__main__"`` guard
    at its end — so this costs no work and triggers no network or file access.
    """
    spec = importlib.util.spec_from_file_location("_r74_audit_classifier", AUDIT_SCRIPT)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load the tier classifier from {AUDIT_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.categorize_test


categorize_test = load_categorize()


def _env_flag(name: str) -> bool:
    """Truthiness of an env switch: "0"/""/unset are false.

    ``bool(os.environ.get(k))`` would read "0" as true, which turns a
    disable-able switch into a one-way door.
    """
    return os.environ.get(name, "").strip().lower() not in ("", "0", "false", "no")


def get_budgets() -> dict[str, float]:
    """Budget per tier, env-overridable. Unknown tiers get the unit budget."""
    unit = float(os.environ.get("SLEEP_GATE_UNIT_BUDGET", str(DEFAULT_UNIT_BUDGET)))
    return {
        "unit": unit,
        "integration": float(
            os.environ.get("SLEEP_GATE_INTEGRATION_BUDGET", str(DEFAULT_INTEGRATION_BUDGET))
        ),
        "e2e": float(os.environ.get("SLEEP_GATE_E2E_BUDGET", str(DEFAULT_E2E_BUDGET))),
    }


def budget_for(category: str, budgets: dict[str, float]) -> float:
    """The budget that applies to one tier.

    ``.get(category, unit)`` is the whole of the slow-bucket rule: the audit's
    ``slow`` and any future category are judged at the unit budget, so every
    exemption has to appear in the shrink-only file.
    """
    return budgets.get(category, budgets["unit"])


def worst_durations(results_dir: Path) -> tuple[dict[str, tuple[float, str]], int]:
    """``test id -> (worst duration, tier)`` over every XML in the corpus.

    Duplicates take the MAX: junit emits one ``<testcase>`` per invocation, so a
    parameterised id appears several times and a shard retry can repeat an id
    outright. The first or the mean would let a test that breached once look
    cheap.

    Zero-duration testcases are skipped exactly as the audit skips them — that is
    a skipped test, not a fast one.
    """
    worst: dict[str, tuple[float, str]] = {}
    xml_count = 0
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
                category = categorize_test(classname, name, str(xml_file))
                if category == "benchmark":
                    continue  # measured latency on purpose; the audit drops these
                test_id = f"{classname}::{name}"
                current = worst.get(test_id)
                if current is None or duration > current[0]:
                    worst[test_id] = (duration, category)
    return worst, xml_count


def load_baseline(path: Path) -> list[str]:
    """The shrink-only exemption ids. A missing file means NO exemptions.

    Not an empty-and-quietly-passing set: an unreadable/absent baseline must
    never widen the gate, which is the audit's own fail-closed rule for its
    baseline machinery.
    """
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Error: {path} is not valid JSON: {exc}") from exc
    if not isinstance(data, list) or not all(isinstance(i, str) for i in data):
        raise SystemExit(f"Error: {path} must be a JSON array of test ids")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail tests over their real-sleep budget (ruling 74).",
    )
    parser.add_argument("results_dir", help="directory of junit XMLs (scanned recursively)")
    parser.add_argument(
        "--baseline",
        default=os.environ.get("SLEEP_GATE_BASELINE", str(BASELINE_DEFAULT)),
        help="shrink-only exemption file (default: duration-budget-baseline.json beside "
        "this script)",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        default=_env_flag("SLEEP_GATE_UPDATE"),
        help="write the baseline down to the ids still over budget; refuses to ADD an id",
    )
    args = parser.parse_args(argv)

    results_dir = Path(args.results_dir)
    if not results_dir.is_dir():
        print(
            f"Error: results directory not found: {results_dir} — the gate ran with no "
            "test data; failing rather than passing vacuously.",
            file=sys.stderr,
        )
        return 1

    worst, xml_count = worst_durations(results_dir)
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

    budgets = get_budgets()
    baseline_path = Path(args.baseline)
    exempt = set(load_baseline(baseline_path))

    # Every id whose worst sample is over its tier budget, exempt or not — the
    # update mode needs the full set (an exempt id that dropped out is a shrink),
    # and the report needs the subset nobody has exempted.
    over_budget_ids = {
        test_id
        for test_id, (duration, category) in worst.items()
        if duration > budget_for(category, budgets)
    }
    breaches = sorted(
        (
            (duration, test_id, category, budget_for(category, budgets))
            for test_id, (duration, category) in worst.items()
            if test_id in over_budget_ids and test_id not in exempt
        ),
        key=lambda b: -b[0],
    )

    print("=" * 70)
    print("REAL-SLEEP DURATION BUDGET GATE (ruling 74)")
    print("=" * 70)
    print(
        f"Budgets: unit={budgets['unit']}s, integration={budgets['integration']}s, "
        f"e2e={budgets['e2e']}s"
    )
    print(f"Corpus: {xml_count} XML file(s), {len(worst)} test(s) with a recorded duration")
    print(f"Exemptions: {len(exempt)} id(s) from {baseline_path} (shrink-only)")
    print("No previous-run downgrade: every breach outside the file is RED.")
    print()

    if args.update:
        additions = sorted(over_budget_ids - exempt)
        if additions:
            # Refuse loudly and write nothing. The file may only shrink; a new
            # id needs a human's diff, exactly as ratchet-check.py's --update
            # refuses to raise a suppression count.
            print(
                f"REFUSING TO UPDATE {baseline_path}: {len(additions)} over-budget id(s) "
                "are NOT already exempt. The baseline may only SHRINK — fix the test "
                "(fake clock, injected sleep) or land the addition as a reviewed edit "
                "to the file itself.",
                file=sys.stderr,
            )
            for tid in additions:
                print(f"  refused add: {tid}", file=sys.stderr)
            print(file=sys.stderr)
            return 1
        shrunk = sorted(exempt & over_budget_ids)
        if len(shrunk) < len(exempt):
            baseline_path.write_text(json.dumps(shrunk, indent=2) + "\n", encoding="utf-8")
            dropped = sorted(exempt - set(shrunk))
            print(f"baseline lowered {len(exempt)} -> {len(shrunk)}; dropped: {dropped}")
        else:
            print("baseline already at the floor")
        print("RESULT: PASS - baseline shrunk or unchanged")
        return 0

    if breaches:
        print(f"BREACHES (over budget, not exempt): {len(breaches)}")
        print("-" * 40)
        for duration, test_id, category, budget in breaches:
            print(f"  {duration:.2f}s (budget: {budget}s) [{category}]")
            print(f"    {test_id}")
        print()
        print("=" * 70)
        print(
            f"RESULT: FAIL - {len(breaches)} test(s) over their real-sleep budget. A "
            "seconds-scale unit test is a real sleep: give it a fake/injected clock, or "
            "land a reviewed shrink-only edit to "
            f"{baseline_path.name} — --update cannot add it."
        )
        return 1

    print("RESULT: PASS - no test over its real-sleep budget")
    return 0


if __name__ == "__main__":
    sys.exit(main())
