#!/usr/bin/env python3
"""Draft the coordinator's status comment from a snapshot (UR-166; ruling 164).

    uv run python scripts/uplevel/status_draft.py [--repo OWNER/REPO] [--since UTC] \
        [--questions FILE]

Reads the same state ``coordinator_snapshot.py`` reads (it imports and calls it, so the two can
never disagree about what the tick saw) and prints the comment body the coordinator posts or
edits in place on #6854. The script is read-only like the snapshot: it prints, it never posts.

The shape is UR-166's, in its order:

1. the live ``BINDING NOW`` records (UR-40), or the loud "none live", then every open
   ``URGENT PATH`` item with its link;
2. ``main``'s state -- green, or red with the failing job;
3. open questions for the owner -- supplied by hand (``--questions`` reads a file of bullet
   lines), because asking is the coordinator's judgement, not something a script can read out
   of the API;
4. owner-tier PRs awaiting the owner's approval -- those with the ``owner`` label and a
   reviewer's verdict;
5. real-tier runs the owner must run (UR-30) and operator results waiting on the owner;
6. status rows owed;
7. stalled agents and heartbeats older than 20 minutes (UR-38, UR-162);
8. the queue: packages ready but unclaimed (UR-63), idle lanes (UR-64), parked claims (UR-67);
9. one closing line of counts: open programme PRs, and PRs merged since the newest owner record
   on #6854, auto-merged ones included.

Parts 5, 6 and 8 are the coordinator's hand-written sections too: the script renders the
snapshot's facts and leaves a ``TODO`` line where only a judgement can fill the row, so the
draft never prints a claim the snapshot did not read (UR-29). UR-166 keeps the whole thing near
4,000 characters; ``over_limit`` reports the excess rather than truncating, because a cut from
the end would silently drop part 9 and leave a partial report that reads complete.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import coordinator_snapshot as snap  # the sibling module in this directory

MARKER = "<!-- status:uplevel-coordinator -->"
NO_QUESTIONS = "(no open questions for the owner)"
LIMIT = 4000
OWNER_LABEL = "owner"


def _binding(lines: list[str], data: dict[str, Any]) -> None:
    live = data["binding_now"]["items"]
    if live:
        for b in live:
            lines.append(
                f"- BINDING NOW {b['created_at']} lapses {b['lapses_at']}: {b['first_line']}"
            )
    else:
        lines.append("- BINDING NOW: none live")
    urgent = [c for c in data["comments"]["items"] if c["flag"] == "URGENT PATH"]
    for c in urgent:
        lines.append(
            f"- URGENT PATH #{c['number']} {c['author']} {c['created_at']}: {c['first_line']}"
        )
    if not urgent:
        lines.append("- URGENT PATH: none open")


def _main(lines: list[str], data: dict[str, Any]) -> None:
    m = data["main"]
    last = m.get("ci_last_completed")
    tip = (m.get("tip") or "?")[:9]
    if last is None:
        lines.append(
            f"- main `{tip}`: CI state unread ({'; '.join(m['errors']) or 'no run found'})"
        )
        return
    if last["conclusion"] in snap.RED_CONCLUSIONS:
        lines.append(
            f"- main `{tip}`: RED -- {last['conclusion']} at {last['head']}, run {last['id']}"
        )
    else:
        lines.append(f"- main `{tip}`: {last['conclusion']} at {last['head']} (run {last['id']})")


def _questions(lines: list[str], questions: Sequence[str]) -> None:
    if not questions:
        lines.append(NO_QUESTIONS)
        return
    for q in questions:
        lines.append(f"- {q}")


def _owner_tier(lines: list[str], data: dict[str, Any]) -> None:
    ready = [
        p
        for p in data["prs"]["items"]
        if OWNER_LABEL in p["labels"] and not p["draft"] and p["gate"] == "SUCCESS"
    ]
    if not ready:
        lines.append("- none")
        return
    for p in ready:
        appr = p.get("approval") or {}
        verdict = (
            "no verdict recorded"
            if not appr
            else f"{appr.get('by')}: {p.get('latest_review') or 'approve'}"
        )
        lines.append(f"- #{p['number']} {p['title']} -- {verdict}")


def _counts(lines: list[str], data: dict[str, Any]) -> None:
    open_prs = len(data["prs"]["items"])
    window = data.get("merged_window") or {}
    count = window.get("count")
    merged = "unread" if count is None else str(count)
    since = f" (since `{window['since']}`)" if window.get("since") else ""
    # UR-166: ONE closing line -- heading and both counts on it, kept last so a hand trim
    # above it can never drop the counts and leave the owner with a report that reads complete.
    lines.append(
        f"== Counts: open programme PRs: {open_prs};"
        f" merged since the newest owner record: {merged}{since}"
    )


def render(data: dict[str, Any], questions: Sequence[str] = ()) -> str:
    """The comment body: MARKER first line, UR-166's nine parts in order, part 9 last."""
    out: list[str] = [MARKER, ""]

    out.append("== BINDING NOW")
    _binding(out, data)
    out.append("")

    out.append("== main")
    _main(out, data)
    out.append("")

    out.append("== Questions for the owner")
    _questions(out, questions)
    out.append("")

    out.append("== Owner tier awaiting approval")
    _owner_tier(out, data)
    out.append("")

    out.append("== Real-tier runs for the owner")
    # UR-30: only the owner runs the real tiers, and what is owed is a judgement about which
    # packages reached that gate -- the snapshot reads none of it. The draft says so instead of
    # inventing a row.
    out.append("- TODO: real-tier runs owed (UR-30) and operator results waiting on you.")
    out.append("")

    out.append("== Status rows owed")
    out.append("- TODO: rows owed this tick (UR-29 evidence lines on PRs that closed a package).")
    out.append("")

    out.append("== Stalled and stale heartbeats")
    hb = data["heartbeats"]
    stale = [h for h in hb["items"] if h["stale"]]
    paused = [h for h in hb["items"] if h["paused"]]
    if not stale and not paused:
        out.append("- none")
    for h in stale:
        out.append(
            f"- {h['agent']} heartbeat {h['updated_at']} age {h['age_min']}m"
            f" (> {snap.STALE_HEARTBEAT_MIN} min, UR-162)"
        )
    for h in paused:
        out.append(f"- {h['agent']} says it is paused (UR-160)")
    out.append("")

    out.append("== Queue")
    # UR-67 makes every open claim a row the coordinator keeps until it closes, and a draft is
    # exactly a parked claim -- so the board's open PRs belong here, not only in §3.
    for p in data["prs"]["items"]:
        state = "draft (parked claim, UR-67)" if p["draft"] else "ready"
        out.append(f"- {state} #{p['number']} {p['title']}")
    out.append(
        "- TODO: packages ready and unclaimed two ticks (UR-63), idle lanes (UR-64),"
        " parked claims (UR-67)."
    )
    watch = data["auto_merge_watch"]
    if watch["disable"] or watch["unknown"]:
        # Not UR-166's own part, but the one thing in the snapshot that needs the owner's
        # hand: UR-108 voids an author's auto-arm, and only the owner rules to void one.
        out.append("")
        out.append("== Auto-merge (UR-108)")
        if watch["disable"]:
            out.append(
                "- armed on an uncarried head: " + ", ".join(f"#{n}" for n in watch["disable"])
            )
        if watch["unknown"]:
            out.append(
                "- armed with the carry unread: " + ", ".join(f"#{n}" for n in watch["unknown"])
            )
    out.append("")

    out.append("== Counts")
    _counts(out, data)
    return "\n".join(out) + "\n"


def over_limit(body: str) -> int | None:
    """Characters over UR-166's ~4,000, or None. Never truncates: a body cut from the end
    loses part 9 and still reads complete, which is the failure mode to avoid."""
    excess = len(body) - LIMIT
    return excess if excess > 0 else None


def read_questions(path: str | None) -> list[str]:
    """One question per non-empty line of a file; the coordinator writes these by hand."""
    if not path:
        return []
    text = Path(path).read_text()
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="scripts/uplevel/status_draft.py",
        description="Draft the coordinator's status comment (UR-166) from a snapshot.",
    )
    parser.add_argument("--repo", type=snap._repo_arg, default=snap.DEFAULT_REPO)
    parser.add_argument("--since", type=snap._since_arg)
    parser.add_argument("--questions", help="file, one owner question per line")
    parser.add_argument("--json", action="store_true", help="print {body, over_limit} as JSON")
    args = parser.parse_args(argv)
    data = snap.Snapshot(args.repo, snap.run_command, snap.utc_now, args.since).build()
    body = render(data, read_questions(args.questions))
    excess = over_limit(body)
    if args.json:
        sys.stdout.write(json.dumps({"body": body, "over_limit": excess}, indent=1) + "\n")
    else:
        sys.stdout.write(body)
        if excess:
            sys.stderr.write(
                f"status_draft: {excess} characters over UR-166's ~{LIMIT};"
                " trim by hand -- part 9 stays last\n"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
