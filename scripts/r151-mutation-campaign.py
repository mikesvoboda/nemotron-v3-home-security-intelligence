#!/usr/bin/env python3
"""Revert-campaign driver for ruling 151's per-tier re-run pins (contract rule 3).

    python3 scripts/r151-mutation-campaign.py

Run from the repo root. It picks the repo's ``.venv/bin/python`` when that can
import pytest, because the suite needs the project's dependencies and the
interpreter you launched this with usually is not that one; ``--python`` names
one explicitly. ``--suite`` repeats to cover more than one test file.

Why this file exists in the repo instead of in a scratch directory: UR-10 says
tools live in the repo, and the claim it exists to check — "these pins have
teeth" — is only evidence if a reader can bite. So every mutant below is applied
to ``scripts/check-test-duration-budget.py`` INSIDE A THROWAWAY GIT WORKTREE at
HEAD, the live tree is never written to, and the driver exits non-zero if any
mutant escapes or any anchor stops matching.

Why a worktree and not a copy of one file: the unit file resolves the repo root
through ``parents[4]`` and imports the audit's classifier through it, so a lone
file copy gives collection errors and a campaign that measures nothing. A
detached worktree is the cheapest tree where the suite can actually run;
``git archive`` will not do, because ``.gitattributes`` ships
``backend/tests/ export-ignore``.

Why ``-p no:randomly``: the campaign compares SETS of failed test ids between
runs. ``pytest-randomly`` reorders and reseeds per run, which is exactly the
noise that would let a mutant look caught or look escaped by accident.

Every mutant below was chosen against a measurement, not a guess, and the set
carries the three that actually escaped before this package shipped: the FAIL
line that called any tier "a seconds-scale unit test" (finding 3.3), the
per-tier re-run map that summed back to one number (finding 3.4, since retired
by deleting the computation), and a POOLED per-tier eligible count, which ran
the whole suite green until an uneven-corpus pin was added to kill it. The
two out-of-tier mutants (``e2e`` joins, ``slow`` joins) are kept because their
CAUGHT lists are the record of which pin owns which tier.

Every anchor was re-anchored at the commit that adds this file; an anchor that
no longer matches is reported as ``ANCHOR`` and fails the run, because a
silently-skipped mutant is how "caught N/N; escaped: none" once became a false
line in a PR body.
"""

from __future__ import annotations

import argparse
import ast
import pathlib
import re
import subprocess
import sys
import tempfile

TARGET = "scripts/check-test-duration-budget.py"

# (what breaking it would mean, the exact text, its replacement)
MUTANTS: list[tuple[str, str, str]] = [
    # -- the two tiers the clause names must stay exactly that set ----------
    (
        "e2e joins RERUN_TIERS: a browser-less job spawns a doomed subprocess",
        'RERUN_TIERS = ("unit", "integration")',
        'RERUN_TIERS = ("unit", "integration", "e2e")',
    ),
    (
        "slow joins RERUN_TIERS: a census-slow test buys a 60 s sleep, not a verdict",
        'RERUN_TIERS = ("unit", "integration")',
        'RERUN_TIERS = ("unit", "integration", "slow")',
    ),
    (
        "integration leaves RERUN_TIERS: ruling 151 silently unshipped",
        'RERUN_TIERS = ("unit", "integration")',
        'RERUN_TIERS = ("unit",)',
    ),
    # -- the cap is PER TIER (UR-125's "in each tier") ----------------------
    (
        "the cap slice pools both tiers: integration spends the unit tier's allowance",
        "        eligible = [b for b in breaches if b[2] == tier]",
        "        eligible = [b for b in breaches if b[2] in RERUN_TIERS]",
    ),
    # -- the header reports per-tier eligible counts ------------------------
    (
        "the header's per-tier count pools the tiers instead of counting each",
        "tier_counts = {tier: sum(1 for b in breaches if b[2] == tier) for tier in RERUN_TIERS}",
        "_pooled = sum(1 for b in breaches if b[2] in RERUN_TIERS) // len(RERUN_TIERS)\n"
        "    tier_counts = {tier: _pooled for tier in RERUN_TIERS}",
    ),
    (
        "the header prints only the re-run count, dropping the eligible count",
        'f"Re-run of a breach: ENABLED — {eligible_count} eligible breach(es) "',
        'f"Re-run of a breach: ENABLED — {re_run_count} eligible breach(es) "',
    ),
    # -- an unverified re-run stays RED -------------------------------------
    (
        "a re-run that FAILED FAST becomes a clearance: fail-closed inverted",
        "            elif seconds is None:\n"
        '                states[test_id] = ("unverified", None, code)\n'
        "            elif code != 0:\n"
        '                states[test_id] = ("unverified", seconds, code)\n',
        "            elif seconds is None:\n"
        '                states[test_id] = ("cleared", None, code)\n'
        "            elif code != 0:\n"
        '                states[test_id] = ("cleared", seconds, code)\n',
    ),
    (
        "a TIMED-OUT re-run becomes a clearance: the stall is called a pass",
        '                states[test_id] = ("timed_out", None, code)',
        '                states[test_id] = ("cleared", None, code)',
    ),
    (
        "a SKIPPED re-run becomes a clearance: executed nothing reads as passed",
        '                states[test_id] = ("skipped", None, code)',
        '                states[test_id] = ("cleared", None, code)',
    ),
    # -- the reproduction comparison itself ---------------------------------
    (
        "the re-run comparison flips to >=: a breach exactly at budget clears",
        "            elif seconds > budget:",
        "            elif seconds >= budget:",
    ),
    # -- what the report says about the rule -------------------------------
    (
        "the FAIL line calls any tier a unit test again (finding 3.3)",
        'f"{notes} A seconds-scale test in a re-run tier is a real sleep: "',
        'f"{notes} A seconds-scale unit test is a real sleep: "',
    ),
    (
        "the cap drifts from UR-125's number (3.11's substance)",
        "MAX_RERUNS = 5",
        "MAX_RERUNS = 4",
    ),
]
# Deliberately NOT a mutant here: finding 3.11's wording fix rewrote the
# ASSERTION MESSAGE of test_the_cap_value_is_the_number_the_rulebook_states,
# which lives in a test's own prose. Nothing imports that string to break, so a
# campaign over the product cannot produce an honest CAUGHT for it — printing one
# would be the false-green shape this driver exists to prevent. What IS mutant-
# covered is the substance that message defends: the cap VALUE, via the row
# above, which the rulebook pin is expected to be the only test to kill (every
# other pin here builds its corpus FROM the constant and so stays self-consistent
# when it moves — that self-consistency is exactly what the pin exists to catch).


def executed_count(summary: str) -> int:
    """How many tests a pytest summary line says RAN, from its real numbers.

    ``1 failed, 68 passed, 1 warning in 10.78s`` is 69, not 1: warnings and the
    timing are not executions, and counting them would let a suite that
    collected nothing look measured. This is the quantity every ESCAPED verdict
    in this driver is a claim about, so ``--self-test`` pins it against the
    strings pytest actually prints.
    """
    return sum(int(count) for count in re.findall(r"\b(\d+) (?:passed|failed|errors?)\b", summary))


def self_test() -> int:
    """Pin executed_count against real summary lines; non-zero if the parse drifted."""
    cases = [
        (
            "============================ 69 passed, 1 warning in 10.73s ============================",
            69,
        ),
        (
            "======================= 1 failed, 68 passed, 1 warning in 10.78s =======================",
            69,
        ),
        ("============ 2 failed, 73 passed, 1 deselected in 11.20s ============", 75),
        ("============================ no tests ran in 0.02s =============================", 0),
        ("========================= 3 errors in 0.41s =========================", 3),
    ]
    bad = [
        (line, executed_count(line), want) for line, want in cases if executed_count(line) != want
    ]
    for line, got, want in bad:
        print(f"SELFTEST | executed_count({line!r}) = {got}, want {want}", file=sys.stderr)
    print(f"self-test: {len(cases) - len(bad)}/{len(cases)} summary shapes parse correctly")
    return 1 if bad else 0


def run_suite(worktree: pathlib.Path, suites: list[str], python: str) -> tuple[set[str], int, str]:
    """FAILED test ids, executed count, and the summary line for one run in WORKTREE.

    The count is returned, not discarded, because the campaign's whole signal is
    an ABSENCE ("this mutant reddened nothing") and an absence is exactly what a
    broken instrument produces: run this file with an interpreter that cannot
    import pytest and every suite run collects zero tests, so every mutant
    reports ESCAPED and the driver accuses good pins of having no teeth. A count
    of zero, or a count that moves between runs, is refused as INSTRUMENT rather
    than read as a measurement.
    """
    result = subprocess.run(
        [python, "-m", "pytest", *suites, "-q", "--tb=no", "-p", "no:randomly"],
        cwd=worktree,
        capture_output=True,
        text=True,
        check=False,
    )
    failed = {
        line.split("::")[-1] for line in result.stdout.splitlines() if line.startswith("FAILED")
    }
    summary = next(
        (
            line
            for line in reversed(result.stdout.splitlines())
            if re.search(r"\d+ (passed|failed|error)", line) or "no tests ran" in line
        ),
        "",
    )
    executed = executed_count(summary)
    if not summary:  # pytest never got to reporting: surface its output, not silence
        tail = (result.stderr or result.stdout).strip().splitlines()
        summary = tail[-1] if tail else "<no output>"
    return failed, executed, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--suite",
        action="append",
        default=None,
        help="test file to mutate against, relative to the worktree root; repeatable",
    )
    parser.add_argument(
        "--python",
        help="interpreter to run the suite with; defaults to the first candidate that can import pytest",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="check the driver's own summary parsing and exit",
    )
    args = parser.parse_args()
    if args.self_test:
        return self_test()

    suites = args.suite or [
        "backend/tests/unit/scripts/test_duration_budget_gate.py",
        "backend/tests/unit/scripts/test_workflow_duration_budget_step.py",
    ]
    root = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
    ).stdout.strip()
    script = pathlib.Path(root) / TARGET
    pristine = script.read_text(encoding="utf-8")
    # A campaign's verdict is a claim about a SPECIFIC test set, so the tests it
    # runs have to be the ones on disk. A detached worktree at HEAD would
    # otherwise run the COMMITTED pins while mutating the WORKING-TREE gate: edit
    # a pin, re-run, and the driver certifies the test you wrote last commit and
    # says nothing about the one you just wrote. Both sides are read from the
    # working tree now, and the drift is printed rather than hidden.
    stale = []
    for suite in suites:
        head = subprocess.run(
            ["git", "show", f"HEAD:{suite}"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        disk = pathlib.Path(root, suite).read_text(encoding="utf-8")
        if head.returncode != 0 or head.stdout != disk:
            stale.append(suite)

    candidates = [args.python] if args.python else [f"{root}/.venv/bin/python", sys.executable]
    python = next(
        (
            c
            for c in candidates
            if c
            and subprocess.run(
                [c, "-c", "import pytest"], capture_output=True, check=False
            ).returncode
            == 0
        ),
        None,
    )
    if python is None:
        print(f"INSTRUMENT | no interpreter can import pytest: tried {candidates}", file=sys.stderr)
        return 2

    failures = 0
    with tempfile.TemporaryDirectory(prefix="r151-campaign-") as tmp:
        worktree = pathlib.Path(tmp) / "wt"
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(worktree), "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        target = worktree / TARGET
        try:
            target.write_text(pristine, encoding="utf-8")
            for suite in suites:  # worktree is at HEAD; the disk copy is the under-test one
                dest = worktree / suite
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(pathlib.Path(root, suite).read_text(encoding="utf-8"), "utf-8")
            if stale:
                print(
                    f"note: {len(stale)}/{len(suites)} suite file(s) differ from HEAD; "
                    "running the working-tree copies, as edited"
                )
            baseline, baseline_count, baseline_summary = run_suite(worktree, suites, python)
            if baseline_count == 0:
                print(
                    f"INSTRUMENT | baseline executed 0 tests: {baseline_summary}", file=sys.stderr
                )
                return 2
            print(f"python: {python}\nsuites: {', '.join(suites)}")
            print(f"baseline: {baseline_count} executed, {len(baseline)} red")
            for description, old, new in MUTANTS:
                count = pristine.count(old)
                if count != 1:
                    print(f"  ANCHOR x{count} | {description}")
                    failures += 1
                    continue
                target.write_text(pristine.replace(old, new), encoding="utf-8")
                try:
                    # ast.parse, not compile(): this is a SYNTAX pre-check only, and
                    # the point is that the mutant is never run by this process —
                    # pytest runs it.
                    ast.parse(target.read_text(encoding="utf-8"), filename="mutant.py")
                except SyntaxError as error:
                    print(f"  SYNTAX   | {description}: {error}")
                    failures += 1
                    target.write_text(pristine, encoding="utf-8")
                    continue
                reds, executed, summary = run_suite(worktree, suites, python)
                if executed != baseline_count:
                    print(
                        f"INSTRUMENT | mutant ran {executed} tests, baseline ran "
                        f"{baseline_count}: {summary}",
                        file=sys.stderr,
                    )
                    failures += 1
                    target.write_text(pristine, encoding="utf-8")
                    continue
                new_reds = sorted(reds - baseline)
                if new_reds:
                    print(f"CAUGHT({len(new_reds)}) | {description}")
                    for name in new_reds:
                        print(f"           {name}")
                else:
                    print(f"ESCAPED     | {description}")
                    failures += 1
                target.write_text(pristine, encoding="utf-8")
            restored, restored_count, _ = run_suite(worktree, suites, python)
            print(
                f"restored: {restored_count} executed, {len(restored)} red "
                f"(baseline {baseline_count}/{len(baseline)}) same={restored == baseline}"
            )
            if restored_count != baseline_count:
                print("INSTRUMENT | restored run executed a different count", file=sys.stderr)
                failures += 1
            if restored != baseline:
                failures += 1
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree)],
                capture_output=True,
                text=True,
                check=False,
            )

    print(f"\n{len(MUTANTS)} mutants, {failures} problem(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
