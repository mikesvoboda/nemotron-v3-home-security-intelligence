#!/usr/bin/env python3
"""Revert-campaign driver for ruling 193's PR watcher (contract rule 3).

    python3 scripts/r193-mutation-campaign.py

Run from the repo root. It applies each mutant below to ``scripts/uplevel/pr_watch.py``
INSIDE A THROWAWAY GIT WORKTREE, runs ``scripts/test_pr_watch.py`` there, and restores the
pristine bytes after every one; the live tree is never written to, and the driver exits
non-zero if any mutant escapes or any anchor stops matching.

Why the campaign lives in the repo instead of a scratch directory: UR-10 (contract rule 3)
says the tools a package's evidence relies on live in the repo, and the claim it exists to
check -- "these pins have teeth" -- is only evidence if a reader can bite. It follows
``scripts/r151-mutation-campaign.py`` in shape for the reasons that file lists: a detached
worktree is the cheapest tree where the suite can actually run, and each mutant's verdict is
an ABSENCE ("this mutant reddened nothing"), which is exactly what a broken instrument
invents. So the driver refuses to read a zero-test run as a measurement.

Two guards r151 does not need and this one does, because this sandbox has filled its overlay
with review worktrees before: disk is checked BEFORE ``worktree add`` (a creation that fails
with ENOSPC takes the following ``cd`` down with it and the mutations then run in the live
checkout -- seen on 2026-10-13), and the worktree's own ``git rev-parse --show-toplevel`` is
asserted before the first write.

Why both sides are read from the working tree: a worktree at HEAD would run the COMMITTED
pins while mutating the WORKING-TREE watcher, certifying the tests you wrote last commit and
saying nothing about the ones you just wrote. The drift is printed, never hidden.

Why ``-p no:randomly``: the campaign compares SETS of failed test ids between runs, and a
shuffled order changes which tests a timeout kills.
"""

from __future__ import annotations

import argparse
import ast
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

TARGET = "scripts/uplevel/pr_watch.py"
SUITES = ["scripts/test_pr_watch.py"]

# (name, what it breaks, [(anchor, mutation), ...]). Every anchor must occur EXACTLY ONCE in
# the pristine file, or the mutant is reported BAD-PATTERN rather than silently un-applied.
MUTANTS = [
    (
        "search-api",
        "adds the search API ruling 193 forbids (30/min shared across every agent)",
        [
            (
                '    lines.append("    issue(number: $ri) {")',
                "    lines.append('  search(query: $q, type: ISSUE) { nodes { ... on "
                'PullRequest { number } } } \')\n    lines.append("    issue(number: $ri) {")',
            )
        ],
    ),
    (
        "body-leak",
        "carries comment BODIES into the printed line instead of the author",
        [
            (
                '        "comments": sorted((c[0], c[1]) for c in _comments(node.get("comments"))),',
                '        "comments": sorted((c[0], c[2]) for c in _comments(node.get("comments"))),',
            )
        ],
    ),
    (
        "seed-reports",
        "the first poll reports pre-existing state as news",
        [
            (
                "    if seeding:\n        state.update(after)\n        return []",
                '    if seeding:\n        state.update(after)\n        return [f"#{n} seeded" for n'
                " in watched]",
            )
        ],
    ),
    (
        "no-error-exit",
        "consecutive API failures never end the watch",
        [("            if errors >= max_errors:", "            if False:")],
    ),
    (
        "no-lifetime-line",
        "a bounded lifetime exits silently (silence = success)",
        [
            (
                '            return 0, [f"no change in {int(lifetime)}s across {total} watched PR(s)"]',
                "            return 0, []",
            )
        ],
    ),
    (
        "lifetime-counts-launch",
        "the no-change line reports the --pr flags, not the discovered watched set",
        [
            (
                "            total = len(watched) if watched else len(prs)",
                "            total = len(prs)",
            )
        ],
    ),
    (
        "busy-spin",
        "polls without waiting the interval (trips the token's rate limit)",
        [("        sleep(interval)", "        sleep(0)")],
    ),
    (
        "no-head-diff",
        "a new head commit is not reported",
        [
            (
                '        if new["head"] != old["head"]:',
                "        if False:",
            )
        ],
    ),
    (
        "inflight-reported",
        "a check still running is reported as a verdict it has not reached",
        [
            (
                '        if name and conclusion and conclusion != "PENDING":',
                "        if name:",
            )
        ],
    ),
    (
        "flat-shape",
        "parses the WRONG wire shape (data, not data.repository)",
        [('    data = response.get("data") or {}', "    data = response or {}")],
    ),
    (
        "no-label-diff",
        "a label change is not reported",
        [('        if new["labels"] != old["labels"]:', "        if False:")],
    ),
    (
        "no-close-line",
        "a merge/close is not reported",
        [('        if new["state"] != old["state"]:', "        if False:")],
    ),
    (
        "binding-any-comment",
        "any new ruling-issue comment counts as BINDING NOW",
        [('if BINDING_MARKER in (body or "")', "if True")],
    ),
    (
        "binding-silently-missing",
        "a new BINDING NOW is not reported at all",
        [("            if cid not in known:", "            if False:")],
    ),
    # --- the label-discovery half ruling 193 asked for -------------------------------
    (
        "no-discovery",
        "labels are ignored: only explicit --pr numbers are ever watched",
        [
            (
                "    for number, group in discovered(data, label_groups).items():",
                "    for number, group in {}.items():",
            )
        ],
    ),
    (
        "discovery-shrinks-the-set",
        "the watched set follows the OPEN-only query, so a merge is never reported",
        [('    after["watched"] = watched', '    after["watched"] = list(known)')],
    ),
    (
        "wipes-read-fields",
        "a --pr that a label also matches is downgraded to UNREAD on the seed poll",
        [
            (
                '        if number in before["prs"] or _read(after["prs"].get(number)):',
                '        if number in before["prs"]:',
            )
        ],
    ),
    (
        "no-new-watch-line",
        "a PR that joins the watched set mid-run is never named",
        [("            lines.append(_watch_line(number, group))", "            pass")],
    ),
    (
        "merged-before-read-silent",
        "a PR that merged before its first field read vanishes into the seed",
        [
            (
                '            elif fields["state"] in ("MERGED", "CLOSED"):',
                "            elif False:",
            )
        ],
    ),
    (
        "labels-inlined",
        "inlines label strings instead of binding them as variables",
        [
            (
                '        args = ", ".join(f"$a{i}_{j}" for j in range(len(group)))',
                '        args = ", ".join(f\'"{label}"\' for label in group)',
            )
        ],
    ),
    (
        "label-list-as-json",
        "sends a LIST value where a scalar belongs (gh's -F JSON form matches nothing, silently)",
        [
            (
                '            variables[f"a{i}_{j}"] = label',
                '            variables[f"a{i}_{j}"] = [label]',
            )
        ],
    ),
    (
        "unfiltered-discovery",
        "drops states:[OPEN], so a lane query returns the whole merged history",
        [
            (
                '        lines.append(f"    a{i}: pullRequests(labels: [{args}], states: [OPEN],")',
                '        lines.append(f"    a{i}: pullRequests(labels: [{args}],")',
            )
        ],
    ),
    (
        "old-window-order",
        "orders discovery by CREATED_AT, so a re-activated PR falls off a full window",
        [
            (
                "direction: DESC",
                "direction: ASC",
            )
        ],
    ),
    (
        "truncation-quiet",
        "a full discovery window reads as a calm tick instead of raising",
        [
            (
                "        if len(nodes) >= DISCOVERY_WINDOW and (total is None or total > DISCOVERY_WINDOW):",
                "        if False:",
            )
        ],
    ),
    (
        "review-label-joins-lane-group",
        "folds the review label into the lane group, so a PR to review is never found",
        [
            (
                "    groups.extend([[label] for label in review_labels if label])",
                "    if groups:\n        groups[0].extend(label for label in review_labels if label)\n"
                "    else:\n        groups.extend([[label] for label in review_labels if label])",
            )
        ],
    ),
    (
        "first-not-last-window",
        "watches the OLD end of a growing connection (the #6854 pagination bug)",
        [
            (
                '    "    comments(last: 100) { nodes { id author { login } body } }",\n'
                "        ]\n    )",
                '    "    comments(first: 100) { nodes { id author { login } body } }",\n'
                "        ]\n    )",
            )
        ],
    ),
    (
        "no-total-count-field",
        "asks no totalCount, so truncation cannot be detected at all",
        [('        lines.append("        totalCount")', "")],
    ),
]


def executed_count(summary: str) -> int:
    """How many tests a pytest summary line says RAN. 1 failed + 68 passed is 69."""
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


def run_suite(worktree: pathlib.Path, python: str) -> tuple[set[str], int, str]:
    """FAILED test ids, executed count, and a summary line, for one run inside WORKTREE."""
    result = subprocess.run(
        [python, "-m", "pytest", *SUITES, "-q", "--tb=no", "-p", "no:randomly"],
        cwd=worktree,
        capture_output=True,
        text=True,
        check=False,
    )
    failed = {
        line.split("::")[-1]
        for line in result.stdout.splitlines()
        if line.startswith("FAILED") or line.startswith("ERROR")
    }
    summary = next(
        (
            line
            for line in reversed(result.stdout.splitlines())
            if re.search(r"\d+ (passed|failed|error)", line) or "no tests ran" in line
        ),
        "",
    )
    if not summary:  # pytest never got to reporting: surface output, not silence
        tail = (result.stderr or result.stdout).strip().splitlines()
        summary = tail[-1] if tail else "<no output>"
    return failed, executed_count(summary), summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--python", help="interpreter with pytest; default: the repo's .venv")
    parser.add_argument(
        "--self-test", action="store_true", help="check the driver's own summary parsing and exit"
    )
    args = parser.parse_args()
    if args.self_test:
        return self_test()

    root = pathlib.Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
        ).stdout.strip()
    )
    pristine = (root / TARGET).read_text(encoding="utf-8")
    suites_from_disk = {s: (root / s).read_text(encoding="utf-8") for s in SUITES}
    stale = [
        s
        for s, text in suites_from_disk.items()
        if subprocess.run(
            ["git", "show", f"HEAD:{s}"], cwd=root, capture_output=True, text=True, check=False
        ).stdout
        != text
    ]

    # ENOSPC is the failure mode that matters here: `worktree add` dies loudly, the following
    # writes then land in the LIVE checkout quietly. Refuse before that can start.
    free_gb = shutil.disk_usage("/").free / 1e9
    if free_gb < 3.0:
        print(
            f"INSTRUMENT | only {free_gb:.1f} GB free on /: refusing to create a worktree",
            file=sys.stderr,
        )
        return 2

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
    with tempfile.TemporaryDirectory(prefix="r193-campaign-") as tmp:
        worktree = pathlib.Path(tmp) / "wt"
        add = subprocess.run(
            ["git", "worktree", "add", "--detach", str(worktree), "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        if add.returncode != 0:
            print(f"INSTRUMENT | worktree add failed: {add.stderr.strip()[:300]}", file=sys.stderr)
            return 2
        # The assertion every past incident calls for: prove WHERE the writes will land.
        toplevel = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=worktree,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        if toplevel != str(worktree):
            print(
                f"INSTRUMENT | worktree toplevel is {toplevel!r}, not {str(worktree)!r}",
                file=sys.stderr,
            )
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree)],
                cwd=root,
                capture_output=True,
                check=False,
            )
            return 2
        target = worktree / TARGET
        try:
            target.write_text(pristine, encoding="utf-8")
            for suite, text in suites_from_disk.items():  # worktree is at HEAD; test the disk copy
                dest = worktree / suite
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(text, encoding="utf-8")
            if stale:
                print(
                    f"note: {len(stale)}/{len(SUITES)} suite file(s) differ from HEAD; running the "
                    "working-tree copies, as edited"
                )
            baseline, baseline_count, baseline_summary = run_suite(worktree, python)
            # POSITIVE CONTROL, twice over: the pristine watcher must be green, and the run must
            # have EXECUTED tests. A dead pytest exits non-zero, and then every mutant reads as
            # CAUGHT -- a perfect score from a dead harness.
            if baseline_count == 0 or baseline:
                print(f"ABORT | pristine suite is not green: {baseline_summary}", file=sys.stderr)
                return 2
            print(f"python: {python}\nsuites: {', '.join(SUITES)}")
            print(
                f"control: {baseline_count} executed, 0 red (pristine green under this command)\n"
            )
            for name, description, pairs in MUTANTS:
                text = pristine
                bad_anchor = ""
                for old, new in pairs:
                    count = text.count(old)
                    if count != 1:
                        bad_anchor = f"anchor matched {count}x, expected 1"
                        break
                    text = text.replace(old, new)
                if bad_anchor:
                    print(f"  BAD-PATTERN | {name}: {bad_anchor}")
                    failures += 1
                    continue
                if text == pristine:
                    print(f"  BAD-PATTERN | {name}: mutation produced no change")
                    failures += 1
                    continue
                target.write_text(text, encoding="utf-8")
                try:
                    ast.parse(text, filename="mutant.py")  # syntax pre-check; pytest runs it
                except SyntaxError as error:
                    print(f"  SYNTAX      | {name}: {error}")
                    failures += 1
                    target.write_text(pristine, encoding="utf-8")
                    continue
                reds, executed, summary = run_suite(worktree, python)
                target.write_text(pristine, encoding="utf-8")
                if executed != baseline_count:
                    print(
                        f"INSTRUMENT | mutant ran {executed} tests, baseline {baseline_count}: "
                        f"{summary}",
                        file=sys.stderr,
                    )
                    failures += 1
                    continue
                new_reds = sorted(reds - baseline)
                if new_reds:
                    print(f"CAUGHT({len(new_reds):>2}) | {name} -- {description}")
                    for test_name in new_reds[:4]:
                        print(f"            {test_name}")
                else:
                    print(f"ESCAPED     | {name} -- {description}")
                    failures += 1
            restored, restored_count, _ = run_suite(worktree, python)
            print(
                f"\nrestored: {restored_count} executed, {len(restored)} red "
                f"(baseline {baseline_count}/0) same={restored == baseline}"
            )
            if restored_count != baseline_count or restored != baseline:
                print("INSTRUMENT | restored run differs from baseline", file=sys.stderr)
                failures += 1
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree)],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )

    print(f"\n{len(MUTANTS)} mutants, {failures} problem(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
