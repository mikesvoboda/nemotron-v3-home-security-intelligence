#!/usr/bin/env python3
"""Revert-campaign driver for ruling 269's waiting-its-turn gate (contract rule 3).

    python3 scripts/r269-mutation-campaign.py

Run from the repo root. Same shape as ``scripts/r151-mutation-campaign.py``:
``lane_tick.py`` sits outside mutmut's widened denominator (``[tool.mutmut]``
names ``backend/services`` and ``backend/api/routes``), so the package's
mutation evidence is a revert campaign over the touched module, every mutant
chosen against a measured behavior and named for the test that owns it, the
live tree never written to (a throwaway worktree at HEAD), and
``-p no:randomly`` because the campaign compares SETS of failed test ids
between runs and pytest-randomly's per-run reseeding is exactly the noise that
would let a mutant look caught or escaped by accident.

The gate under mutation is ``lane_tick.py``'s claim block and its
``waiting_its_turn`` predicate (ruling 269, record 6275028285): the digest may
offer the next claimable package only when every open PR the lane holds is
waiting its merge turn (item 1) and the lane holds fewer than two (item 3).
A false offer here is a UR-52 violation committed by the tool itself -- the
direction every mutant below points.

The ``p["draft"]`` leg of the predicate has no mutant on purpose, and that is
a measured fact, not an omission: ``marker()`` returns ``""`` for a draft
before reading reviews, so ``reviews_of`` holds nothing for one and the
predicate's review leg already refuses it -- the draft check is layered behind
the marker guard, and the marker guard's own mutant (below) is what proves the
layer has teeth (an existing ruling-198 test catches it first).

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

TARGET = "scripts/uplevel/lane_tick.py"
SUITES = ["scripts/test_lane_tick.py"]

# (what breaking it would mean, the exact text, its replacement)
MUTANTS: list[tuple[str, str, str]] = [
    # -- item 1(b): which gate verdicts qualify ------------------------------
    (
        "a CANCELLED last run stops qualifying: the roll's cancelled run is read as a failed gate",
        'if p["gate"] not in ("SUCCESS", "CANCELLED"):',
        'if p["gate"] != "SUCCESS":',
    ),
    (
        "any finished verdict qualifies: a gate that failed does qualify after all",
        'if p["gate"] not in ("SUCCESS", "CANCELLED"):',
        "if p[\"gate\"] not in GATE_DONE or p[\"gate\"] == \"SKIPPED\":",
    ),
    (
        "the gate leg is skipped entirely: an absent gate offers a package",
        'if p["gate"] not in ("SUCCESS", "CANCELLED"):',
        "if False:",
    ),
    (
        "the real-run leg drops: a draft run's SUCCESS-over-skipped rollup counts as a pass",
        'if p["gate"] == "SUCCESS" and not ran_for_real(',
        'if False and p["gate"] == "SUCCESS" and not ran_for_real(',
    ),
    # -- item 1(d): the author's-to-do legs ----------------------------------
    (
        "a merge conflict stops blocking: DIRTY reads as the roll, not the author's to do",
        'if p["draft"] or p["merge_state"] == "DIRTY" or "owner" in p["labels"]:',
        'if p["draft"] or "owner" in p["labels"]:',
    ),
    (
        "an owner question stops blocking: the owner label is read as nothing",
        'if p["draft"] or p["merge_state"] == "DIRTY" or "owner" in p["labels"]:',
        'if p["draft"] or p["merge_state"] == "DIRTY":',
    ),
    (
        "a changes-requested reply stops blocking: is_approval is not asked before at_head",
        "    if not snap.is_approval(snap.first_line(newest.get(\"body\") or \"\")):\n"
        "        return False\n",
        "    pass\n",
    ),
    (
        "a review the audit would refuse still counts: any non-False verdict is a carry",
        "    here = at_head(s, p, newest)\n    return here is True",
        "    here = at_head(s, p, newest)\n    return here is not False",
    ),
    (
        "a failed review read still counts: an unread verdict opens the offer",
        "    if not reviews:\n        return False\n",
        "    pass\n",
    ),
    (
        "the marker guard drops: a draft gets its reviews read, and the offer rests on skipped legs",
        "        if p[\"draft\"]:\n            return \"\"  # a draft is neither reviewed nor armed (ruling 198: skipped jobs pass)",
        "        if False and p[\"draft\"]:\n            return \"\"  # a draft is neither reviewed nor armed (ruling 198: skipped jobs pass)",
    ),
    # -- item 3 and item 6: the offer's own arithmetic -----------------------
    (
        "the cap widens: a lane holding two open packages still gets an offer",
        "if held and all_waiting and len(held) < 2:",
        "if held and all_waiting and len(held) < 3:",
    ),
    (
        "every becomes any: one mid-flight PR beside a waiting one opens the offer",
        "    all_waiting = all(\n",
        "    all_waiting = any(\n",
    ),
    (
        "the held gate opens without holds: a mid-flight defect fix prints a ruling-269 offer",
        "if held and all_waiting and len(held) < 2:",
        "if True and all_waiting and len(held) < 2:",
    ),
    (
        "the waiting gate is skipped: the offer prints beside a mid-flight hold",
        "if held and all_waiting and len(held) < 2:",
        "if held and True and len(held) < 2:",
    ),
]


def executed_count(summary: str) -> int:
    """Tests pytest actually ran, parsed from the summary line it prints.

    The count is the campaign's instrument check: an absence ("this mutant
    reddened nothing") is exactly what a broken instrument produces, and a
    collection that silently shrank is how a mutant looks caught while the
    tests that own it never ran.
    """
    return sum(int(count) for count in re.findall(r"\b(\d+) (?:passed|failed|errors?)\b", summary))


def run_suite(worktree: pathlib.Path, suites: list[str], python: str) -> tuple[set[str], int, str]:
    """FAILED test ids, executed count, and the summary line for one run in WORKTREE."""
    result = subprocess.run(
        [python, "-m", "pytest", *suites, "-q", "--tb=no", "-p", "no:randomly", "-n", "0"],
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
        "--python",
        help="interpreter to run the suite with; defaults to the first candidate that can import pytest",
    )
    args = parser.parse_args()

    suites = SUITES
    root = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
    ).stdout.strip()
    script = pathlib.Path(root) / TARGET
    pristine = script.read_text(encoding="utf-8")
    # A campaign's verdict is a claim about a SPECIFIC test set, so the tests it
    # runs have to be the ones on disk (the r151 driver's stale-copy guard).
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
    with tempfile.TemporaryDirectory(prefix="r269-campaign-") as tmp:
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
