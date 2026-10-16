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

# Files the suite READS but no mutant touches: AGENTS.md documents the suite size, and
# r193-mutation-campaign.py holds the MUTANTS list the counting test parses. The worktree is at
# HEAD, so anything the suite reads has to be copied from the working tree exactly like the suite
# itself -- otherwise the guard compares a working-tree count against a HEAD-prose count and fails
# on provenance rather than on the property it exists to check. Seen on 2026-10-16: the new
# counting test aborted the pristine baseline ("says 37 tests; this file defines 48") because only
# TARGET and SUITES were copied. A file listed here must never also be a mutant's target.
CONTEXT = ["scripts/uplevel/AGENTS.md", "scripts/r193-mutation-campaign.py"]

# (name, what it breaks, [(anchor, mutation), ...]). Every anchor must occur EXACTLY ONCE in
# the pristine file, or the mutant is reported BAD-PATTERN rather than silently un-applied.
MUTANTS = [
    (
        "graphql-errors-swallowed",
        "returns an empty payload instead of raising on a GraphQL errors response, so a broken "
        "watch looks like a quiet one (the silently-empty class this module keeps meeting)",
        [
            (
                '    if payload.get("errors"):\n'
                '        raise RuntimeError(str(payload["errors"])[:400])',
                '    if payload.get("errors"):\n        return {"data": {}}',
            )
        ],
    ),
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
                '        "comments": [(c[0], c[1]) for c in _comments(node.get("comments"))],',
                '        "comments": [(c[0], c[2]) for c in _comments(node.get("comments"))],',
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
        [("return bool(first) and BINDING_MARKER in first[0]", "return bool(body)")],
    ),
    (
        "binding-any-line",
        "matches BINDING NOW anywhere in the body, so a comment QUOTING a ruling wakes the lane "
        "(UR-40 binds on the FIRST line; the live false-positive is #6854 6180424930)",
        [
            (
                '    first = (body or "").lstrip().splitlines()\n'
                "    return bool(first) and BINDING_MARKER in first[0]",
                '    return BINDING_MARKER in (body or "")',
            )
        ],
    ),
    (
        "seeding-keyed-on-emptiness",
        "keys seeding on an empty pr dict, so a label-only watcher over a lane with nothing routed "
        "to it seeds forever and never reads #6854 (finding 4: the idle lane slept through a new "
        "BINDING NOW)",
        [
            (
                '    seeding = "seeded" not in state',
                '    seeding = not state.get("prs")',
            )
        ],
    ),
    (
        "binding-silently-missing",
        "a new BINDING NOW is not reported at all. Re-anchored when the ruling diff grew the "
        "backfill guard: `if cid not in known:` became `if fresh(cid):`, same single gate",
        [("            if fresh(cid):", "            if False:")],
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
        "two-labels-join-one-connection",
        "merges two labels into one connection: OR still FINDS the PR (so no test about finding "
        "it can catch this) but discovered() attributes it to the group that matched, so the watch "
        "line names a label the PR does not carry",
        [
            (
                "    return [[label] for label in given if label]",
                "    groups = [[label] for label in given if label]\n"
                "    if len(groups) > 1:\n        groups[0].extend(groups.pop())\n    return groups",
            )
        ],
    ),
    (
        "discovery-first-label-only",
        "a PR two connections match keeps only the first label, so its line omits a match the "
        "response proved (the ordinary case: #7175 carries lane:ops AND cell:a)",
        [
            (
                "            reasons.extend(label for label in group if label not in reasons)",
                "            if not reasons:\n                reasons.extend(label for label in group)",
            )
        ],
    ),
    (
        "first-not-last-window",
        "watches the OLD end of a growing connection (the #6854 pagination bug). The target line is "
        "now an f-string interpolating EVENT_WINDOW -- the rendered query is byte-identical, and the "
        "anchor follows the SOURCE spelling, which is what the driver mutates",
        [
            (
                'f"    comments(last: {EVENT_WINDOW}) {{ nodes {{ id author {{ login }} body }} }}",',
                'f"    comments(first: {EVENT_WINDOW}) {{ nodes {{ id author {{ login }} body }} }}",',
            )
        ],
    ),
    (
        "no-total-count-field",
        "asks no totalCount, so truncation cannot be detected at all",
        [('        lines.append("        totalCount")', "")],
    ),
    # ---- the three fixes the UR-89 review of e0ba63e05 asked for, reverted to their before state.
    # Each of these was a bug the review FOUND (not one a test caught), so the pin that now covers
    # it is exactly what these reverts are for: if the dedup/`reopened`/ruling-guard line is ever
    # dropped, the suite must go red, and these mutants are the proof it does.
    (
        "dup-pr-not-deduped",
        "lets a repeated --pr through, so the query declares $p7175 twice and every poll dies "
        "with variableNotUnique (the API rejection is what finding 2 was)",
        [("    args.prs = list(dict.fromkeys(args.prs))\n", "")],
    ),
    (
        "state-line-two-outcomes",
        "restores `merged if MERGED else closed`, so a REOPENED PR prints 'closed' -- the opposite "
        "of the event, on the one line the agent acts on",
        [
            (
                '    return {"MERGED": "merged", "CLOSED": "closed", "OPEN": "reopened"}'
                ".get(state, state.lower())\n",
                '    return "merged" if state == "MERGED" else "closed"\n',
            )
        ],
    ),
    (
        "ruling-guard-never-runs",
        "un-hooks _check_ruling, so a poll answered with a null `issue` node seeds a BINDING NOW "
        "channel that never compares again -- silent forever, which is the failure mode named "
        "finding 4",
        [
            (
                "    _check_explicit(data, prs)\n    _check_ruling(data, ruling_issue)\n",
                "    _check_explicit(data, prs)\n",
            )
        ],
    ),
    (
        "explicit-null-skipped",
        "un-hooks _check_explicit, so an explicitly given --pr answered null is stored as None and "
        "skipped by diff_lines: the head change straddling the null window is lost, silently and for "
        "good, because the next poll's `before` IS the null snapshot -- named finding 1",
        [
            (
                "    _check_explicit(data, prs)\n    _check_ruling(data, ruling_issue)\n",
                "    _check_ruling(data, ruling_issue)\n",
            )
        ],
    ),
    (
        "delete-reads-as-new",
        "restores the one-directional diff: a vanished item prints 'new review'/'new comment', so "
        "a deleted comment announces an ADDITION that never happened and names no author -- named "
        "finding 2. Re-anchored when `_event_lines` grew the full-window verdict: the revert now "
        "removes the verdict branch and prints the vanished items as additions, which is the same "
        "bug in the new spelling",
        [
            (
                "    vanished = [item for item in before if item[0] not in new_ids]\n"
                '    verdict = "deleted" if len(after) < EVENT_WINDOW else "missing"\n'
                '    lines += [f"{prefix}{verdict} {noun}{_from(item[1])}" for item in vanished]\n',
                "    vanished = [item for item in before if item[0] not in new_ids]\n"
                '    lines += [f"{prefix}new {noun}{_from(item[1])}" for item in vanished]\n',
            )
        ],
    ),
    (
        "read-gone-null-skipped",
        "un-hooks _check_read_gone_null, so a DISCOVERED PR that was READ on an earlier poll and is"
        " then answered null is stored as None and skipped by diff_lines: the change straddling the"
        " null window is lost silently and for good (the next poll's `before` IS the null snapshot),"
        " and the watch reports a calm tick through the gap -- the UR-89 round's finding 2, whose"
        " stated mechanism (`_pr_fields(None)` crashing) does not reproduce, but whose SILENT-LOSS"
        " class is real on this path",
        [
            (
                "    _check_read_gone_null(before, after)\n",
                "",
            )
        ],
    ),
    (
        "pending-string-widened",
        'replaces the StatusContext in-flight string "PENDING" with "NOPE", so a context that is'
        " still running reports a verdict it has not reached. Survived 48/48 until"
        " test_a_status_context_still_running_is_no_verdict_but_a_reached_one_is added a"
        " `{context, state}` fixture -- every other fixture emits a CheckRun (null `conclusion` +"
        " `status`), so no fixture could reach the string clause, and `inflight-reported` only"
        " catches the null path -- named finding 4",
        [
            (
                '        if name and conclusion and conclusion != "PENDING":',
                '        if name and conclusion and conclusion != "NOPE":',
            )
        ],
    ),
    (
        "full-window-called-deleted",
        'hard-codes the vanish verdict to "deleted", so a comment that merely aged out of a FULL '
        "`last: EVENT_WINDOW` window is announced as deleted. On a PR with more comments than the "
        "window one new comment pushes the oldest out of the response -- reproduced against the "
        "shipped check(): window 1..100, then 2..101, printed `#7175 deleted comment from u1` with "
        "nothing deleted. Kills THREE tests at this head (kill-set rendered by the 47-mutant run): the "
        "both-sides test, the backfill test (whose third assertion demands the word `missing` for the "
        "vanished newest comment), and the anchorless-turnover test, which leans on this same verdict "
        "because its whole scenario is a vanished side; the pre-existing deletion test seeds three "
        "comments, below the cap, where the word is earned -- the UR-89 round's finding 5. At "
        "`81057a51b` it killed TWO (both-sides + backfill, measured by hand) while #7175's body claimed "
        "ONE -- true only before the backfill test existed -- which is round five's finding 2",
        [
            (
                '    verdict = "deleted" if len(after) < EVENT_WINDOW else "missing"',
                '    verdict = "deleted"',
            )
        ],
    ),
    (
        "unread-carry-dropped",
        "drops the UNREAD carry-forward, so a DISCOVERED PR answered null on its first field read "
        "loses the label group that registered it and its later merge prints nothing -- named "
        "finding 4",
        [
            (
                '        if after["prs"].get(number) is None and UNREAD in (before["prs"].get(number) or {}):\n'
                '            after["prs"][number] = before["prs"][number]\n',
                '        if False:\n            after["prs"][number] = before["prs"][number]\n',
            )
        ],
    ),
    (
        "backfill-reads-as-new",
        "restores the membership diff on the PR channels: on a FULL window every id absent from last "
        "poll prints as an arrival, so a DELETED newest comment -- whose removal lets `last: 100` "
        "back-fill the oldest id it had aged out -- announces `new comment` for a comment that is "
        "older than everything on screen. Reproduced against shipped check() at 78dbf9b: seed "
        "C_1..C_100, slide to C_2..C_101, delete C_101 -> printed `#7168 new comment from uC_1`. "
        "The reviewer who reported it called the fix shape 'suppress new-side on a full window', but "
        "that would kill the genuine append too, so the guard is POSITIONAL and this mutant restores "
        "only the positional clause",
        [
            (
                "    idx = {item[0]: i for i, item in enumerate(after)}\n"
                "    top_shared = max(idx[i] for i in anchor)\n"
                "    return [item for item in fresh if idx[item[0]] > top_shared]",
                "    return fresh",
            )
        ],
    ),
    (
        "ruling-backfill-reads-as-new",
        "restores the membership diff on the #6854 ruling channel: an old BINDING that BACK-FILLS "
        "into a full window re-prints `new BINDING NOW`, and a false line there wakes EVERY lane onto "
        "a ruling already carried out -- the direct opposite of UR-40's no-op rule, on the channel "
        "every lane in the repo polls. Kills TWO tests at this head (kill-set rendered by the "
        "47-mutant run): the ruling backfill test and the ruling SHRINK test -- the latter because a "
        "shrink's re-entry is exactly what a membership diff cannot see; at `81057a51b` it killed only "
        "the backfill test. The edited-to-bind and genuine-arrival controls keep printing under the "
        "mutation (an arrival is above top_shared by definition; an edit is `cid in old_set`, which "
        "the mutant never consults)",
        [
            (
                "                return cid in idx and idx[cid] > top_shared",
                "                return True",
            ),
        ],
    ),
    (
        "window-sorted-lexically",
        "re-sorts the comment window LEXICALLY inside `_pr_fields`, which destroys the chronology the "
        "backfill guard reads: C_10 sorts between C_1 and C_2, so `position` stops meaning time and "
        "the newest real arrival (C_101, which sorts BEFORE C_2) falls below top_shared and goes "
        "unreported -- the watcher silently misses appends on exactly the busy PRs where the window "
        "truncates. Pinned because the guard's correctness rests on a live-API property measured once "
        "(#6854: 721 comments, the 100 returned run strictly ascending) -- a future 'cleanup' that "
        "adds a sort back would break it while looking tidier",
        [
            (
                '        "comments": [(c[0], c[1]) for c in _comments(node.get("comments"))],',
                '        "comments": sorted((c[0], c[1]) for c in _comments(node.get("comments"))),',
            )
        ],
    ),
    (
        "shrink-consults-current-window-only",
        "asks only the CURRENT window whether it truncated, which is the round-five finding 1 verbatim: "
        "`full=len(after) >= EVENT_WINDOW`. A backfill is an id absent from the PREVIOUS snapshot, so a "
        "window that read SHORT in hand does not prove the last one held every comment that exists -- on "
        "a FULL -> SHORT shrink the aged-out ids re-enter at the bottom and every one of them passes the "
        "membership fast path. Reproduced against the shipped check() at 81057a51b: seed the full window "
        "of a 150-comment PR, delete the 60 newest, the poll printed 50 `new comment` lines for comments "
        "older than everything on screen. Kills the shrink test on this channel",
        [
            (
                "            truncated=len(before) >= EVENT_WINDOW or len(after) >= EVENT_WINDOW,\n",
                "            truncated=len(after) >= EVENT_WINDOW,\n",
            )
        ],
    ),
    (
        "ruling-shrink-consults-new-window-only",
        "the same too-narrow question on the #6854 channel, where the false line wakes EVERY lane onto a "
        "ruling UR-40 already made a no-op: `full = new_ruling[window_full]` alone. Kills the ruling "
        "shrink test; the edited-to-bind and genuine-arrival controls keep printing under the mutation, "
        "so nothing but the false-wake pin dies",
        [
            (
                '            truncated = new_ruling.get("window_full", False) or '
                'old_ruling.get("window_full", False)\n',
                '            truncated = new_ruling.get("window_full", False)\n',
            )
        ],
    ),
    (
        "anchorless-turnover-reads-as-new",
        "removes the no-anchor guard on the PR channel, restoring the -1 fallback that made an unanchored "
        "comparison announce everything: two consecutive FULL windows sharing no id (a last:100 bulk-deleted "
        "on a >200-comment thread) passed every fresh id and printed 100 `new comment` lines with nothing "
        "added -- measured at 81057a51b as `new=100 missing=100`. Position without a shared id cannot be "
        "proved, so the new side stays silent and the vanished side still speaks. Kills the turnover test",
        [
            (
                "    anchor = old_ids & new_ids\n"
                "    if not anchor:\n"
                "        return []  # nothing shared: position is unprovable, so announce no arrival\n",
                "    anchor = old_ids & new_ids\n",
            )
        ],
    ),
    (
        "ruling-anchorless-turnover-reads-as-new",
        "removes the same no-anchor guard from the ruling predicate, so an unanchored ruling window "
        "re-wakes every lane for every binding it can no longer place. Kills only the ruling half that the "
        "turnover scenario exercises on this channel",
        [
            (
                "                if top_shared < 0:\n"
                "                    return False  # no shared id: position is unprovable, so announce no arrival\n",
                "",
            )
        ],
    ),
    (
        "ruling-ask-detached-from-the-constant",
        "types #6854's ruling-window size back in as a literal instead of interpolating EVENT_WINDOW -- "
        "round six's finding, verbatim. The rendered query is byte-for-byte identical at the constant's "
        "value, so NOTHING that reads the query text can see it: the OLD guard asserted "
        '`f"comments(last: {EVENT_WINDOW})" in query` and the PR channel\'s identical rendering answered '
        "for the ruling channel. That is why this mutant is killed by the AST census and not by any "
        "behavior test -- snapshot()'s `window_full` grades THIS connection's length against EVENT_WINDOW, "
        "so a drift means the false-wake guard reads one window while the comparison describes another. "
        "Kills test_window_size_is_bounded_by_a_named_constant and nothing else, which is the point: it is "
        "the guard's own teeth-test",
        [
            (
                "    lines.append(\n"
                '        f"      comments(last: {EVENT_WINDOW}) {{ nodes {{ id author {{ login }} body }} }}"\n'
                "    )\n",
                '    lines.append("      comments(last: 100) { nodes { id author { login } body } }")\n',
            )
        ],
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
    assert TARGET not in SUITES and TARGET not in CONTEXT, "a mutant target cannot also be copied"
    suites_from_disk = {s: (root / s).read_text(encoding="utf-8") for s in [*SUITES, *CONTEXT]}
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
                    f"note: {len(stale)}/{len(suites_from_disk)} read-file(s) differ from HEAD; "
                    "running the working-tree copies, as edited"
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
