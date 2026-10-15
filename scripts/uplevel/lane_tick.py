#!/usr/bin/env python3
"""The lane cell's whole tick reading in one read-only call (ruling 181; roles/lane.md "The tick").

    uv run python scripts/uplevel/lane_tick.py --sandbox <name> [--repo OWNER/REPO]
    uv run python scripts/uplevel/lane_tick.py --sandbox <name> --beat "<line 2>"

Prints, in tick order: the ``for you:`` lines (ruling 197: each record and each owner pointer of
the last 48 hours whose machine footer names me), my heartbeat id and age, the coordinator's age
(UR-162), disk use of `/` and `/var/lib/docker` (UR-180 pointer above 90%), the live ``BINDING NOW``
records the ruling map does not carry (ruling 177), my own open PRs with their one CI read (UR-38)
and ruling 198's ``needs your review`` / ``arm auto-merge`` markers (each PR's one review is its
author's, so there is no review queue to list), and the next claimable package on my own roster
queue (UR-52). It drives ``coordinator_snapshot.Snapshot`` minus that role's own three sections --
``status_draft.py`` is the sibling precedent for driving it -- and adds the lane's deltas.

Everything it reads arrives through one seam: ``build(run, clock, repo, sandbox)`` takes the runner,
the clock, the repo and the sandbox, so a test needs no monkeypatching and ``main`` cannot hand the
renderer a different type than it expects. Every call goes through that runner; a failed
``gh``/``git``/``df`` call prints ``ERROR <section>``, never an empty section.

``--beat`` is the one write, and it is a separate mode: it edits (or first posts) my heartbeat on
#6958 with the marker line written by the tool, not by hand (ruling 197), and prints one line.
The digest mode never writes.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable, Sequence
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coordinator_snapshot as snap  # sibling: the shared readers, helpers and the one runner

PKGS, MAP = (
    "origin/main:docs/uplevel/packages/{}.md",
    "origin/main:docs/uplevel/history/ruling-map.md",
)
ROSTER = "origin/main:docs/uplevel/roles/lane.md"
# The snapshot's own list query omits the head ref, which the digest needs to know which PRs are
# mine. One extra read, not one per PR. (The PR body left this query with ruling 198: it fed only
# the review queue's `Plan text:` column, and that queue is gone.)
HEADJ = "number,title,headRefName"
MOUNTS = ("/", "/var/lib/docker")
CAP_LINES = 80  # ops.md's "at most 80 lines" for this tool -- read on the printed digest, below.
URGENT_LIFE = timedelta(hours=1)  # UR-162's one-raise-per-hour dedup window.
PLAN_TEXT = re.compile(r"^[ \t>*_#`-]*\*{0,2}Plan text:\*{0,2}[ \t]*(.*)$", re.IGNORECASE | re.M)
# Ruling 198's markers read reviews EXACTLY as the coordinator does: a review is a comment whose
# body starts `Review:` (the snapshot's REVIEWS_JQ), an approval is `is_approval(first_line)`, and
# "for this head" is `Snapshot.judge` -- the sha the review names, else the UR-106 carry. A reading
# of its own ("a `Review: approve` on any line, posted after the head's commit") disagreed with the
# merge audit both ways: it armed a `## Self-review` heading the audit reads as no approving review,
# and it asked for a re-review of an update-branch head the audit reads as carried (see
# `review_marker`).
# `CI Gate` states that mean the run at the head has FINISHED. Anything else -- in progress,
# queued, pending, absent, or a state this list does not know -- is "not finished": the marker
# waits a tick rather than send the author to review a head whose CI-only clauses are unread.
GATE_DONE = frozenset(
    {"SUCCESS", "FAILURE", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", "NEUTRAL", "SKIPPED",
     "STARTUP_FAILURE", "STALE", "ERROR"}
)  # fmt: skip
# A roster row is | agent | tier | queue | review label |, and the label column reads `none` for a
# cell with no review queue (coordinator, heavy-a, heavy-b, operator) -- a fact, not a missing read.
ROW = re.compile(r"\|\s*`([\w.-]+)`\s*\|[^|]*\|(.*)\|\s*`?(review:[\w-]+|none)`?\s*\|")
# A queue entry's token: the BACKTICKED NAME AT THE START of the entry (see ``queue_entries`` -- a
# backtick anywhere else in the cell is prose referring to some other package, not a slot).
QUEUE_TOKEN = re.compile(r"\s*`\[?([\w.]+)\]?`")
# The header wraps: `[r96i11]`'s and a frontend package's `**PR:**` value sits on the NEXT line.
# Bounded by the blank line after the header, so the value is the field's own continuation.
PKG_FIELD = re.compile(r"\*\*PR:\*\*([\s\S]*?)(?:\n\s*\n|\Z)", re.I)
NONE_YET = re.compile(r"[^\n#]*none yet", re.I)
# The number a package block's `**PR:**` field names. `NONE_YET`'s `[^#]` class is the proof the
# field's value carries a literal `#`, so the number is read from the same captured text.
PR_NUMBER = re.compile(r"#(\d+)")
# The package header line, as it stands AFTER splitting on "### " (the marker is gone).
BLOCK = re.compile(r"\[?([\w.]+)\]?\s")
# Ruling 197's machine footers: ONE HTML-comment line (invisible on GitHub) ending an owner record
# on #6854 or an owner pointer on a PR. Before them a record reached a lane only through the map
# filter (a MAPPED ruling vanished from the digest) and a pointer only as a `1c/0r` count -- which
# is how frontend missed `6197231400`. `post_record.py` writes them and parses its own output with
# these, so the writer and this reader cannot drift. Whitespace runs are tolerated; nothing else is.
# A name is a sandbox name without its `agent-`/`uplevel-` prefixes (`footer_name`).
FOOTER_NAME = r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*"
RECORD_FOOTER = re.compile(
    rf"<!--[ \t]*uplevel:[ \t]+ruling=(\d+)[ \t]+lanes=({FOOTER_NAME}(?:,{FOOTER_NAME})*)"
    r"[ \t]+packages=([\w.]+(?:,[\w.]+)*)[ \t]*-->"
)
POINTER_FOOTER = re.compile(
    rf"<!--[ \t]*uplevel:[ \t]+pointer[ \t]+ruling=(\d+)[ \t]+lane=({FOOTER_NAME})[ \t]*-->"
)
FOOTER_START = re.compile(r"<!--[ \t]*uplevel:")
# The names a footer may carry -- the roster's sandboxes through `footer_name`
# (test_post_record pins this tuple against roles/lane.md's rows, so a new sandbox fails there).
NAMES = (
    "frontend", "backend", "docs", "ops-a", "ops-b", "operator", "heavy-a", "heavy-b", "coordinator",
)  # fmt: skip
BEAT_CAP = 600  # UR-155: a whole heartbeat, marker line included, is at most 600 characters.


class LaneSnap(snap.Snapshot):
    """The snapshot minus the coordinator's own reads. ``_main`` shrinks to the ``git fetch`` the
    later sections assume (UR-38's lane CI read is the gate inside ``_prs``); ``_legs`` and the
    ``_merged_audit`` are the coordinator's update-branch and merge verdicts, never a lane's, and so
    is ``_review`` over EVERY open PR -- ``build`` runs the same read and the same ``judge`` for my
    own ready PRs only, which is all ruling 198's markers need. ``_rollup`` is kept, and each PR's
    rollup is remembered, because ``arm auto-merge`` asks whether the gate's run was a draft run.
    ``_comments`` is kept because it sets ``self.now``, which ``_binding_now``/``_heartbeats`` read."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.rollups: dict[int, list[dict]] = {}

    def _review(self, item: dict) -> None:
        """The coordinator's verdict read over every PR; ``build`` reads it for mine (``judge``)."""

    def _rollup(self, pr: dict, errors: list[str]) -> list[dict]:
        rollup = super()._rollup(pr, errors)
        self.rollups[pr["number"]] = rollup
        return rollup

    def _main(self) -> None:
        self.data["main"] = {"errors": []}
        try:
            self.git("fetch", "-q", "origin")  # keep origin/main fresh for the behind count
        except Exception as exc:  # reported, not fatal
            self.data["main"]["errors"].append(f"fetch origin: {snap.error_text(exc)}")

    def _legs(self, item: dict) -> None:
        """UR-102's no-update legs are the coordinator's merge decision, not the lane's tick."""

    def _merged_audit(self) -> None:
        self.data["merged"] = {"items": [], "errors": []}


# --- the lane's own readings -----------------------------------------------------------------


def identities(roster: str, sandbox: str) -> dict[str, str]:
    """My lane/cell/review-label and my queue, from the roster row keyed by the sandbox name.

    Every agent signs with the owner's login (UR-168), so the roster row -- not the author -- is
    what decides which lane's work is mine. The label column is still read (the roster keeps it,
    and ``none`` still marks a cell with no package file) though ruling 198 retired review routing.
    """
    for line in roster.splitlines():
        row = ROW.search(line)
        if row and sandbox.endswith(row.group(1)):
            # Lane and cell come from the row's NAME through the snapshot's own agent_key, so the
            # digest and box 2's signed-activity rule cannot disagree about what an agent is.
            lane, cell = snap.agent_key(row.group(1))
            label = row.group(3)
            return {
                "lane": lane,
                "cell": cell or "",
                "review_label": None if label == "none" else label,
                "queue": queue_entries(row.group(2)),
            }
    raise snap.CommandError(f"no roster row for sandbox {sandbox}")


def footer_name(sandbox: str) -> str:
    """The name a ruling 197 footer uses for an agent: ``agent-uplevel-ops-b`` -> ``ops-b``.

    Read through the snapshot's ``agent_key``, the normalization the digest's beat lookup and box 2's
    signed-activity rule already share, so both live spellings of ``--sandbox`` give one name.
    """
    lane, cell = snap.agent_key(sandbox)
    return f"{lane}-{cell}" if cell else lane


def footer(body: str | None) -> dict | None:
    """The machine footer ending ``body`` (its LAST non-blank line), as fields, or ``None``.

    ``kind`` is ``record``, ``pointer``, or ``malformed`` for a last line that opens like a footer
    but parses as neither -- printed as a NOTE, because a footer the owner meant and the reader
    cannot read would otherwise drop the record back to the silence ruling 197 exists to end.
    """
    lines = [ln.strip() for ln in (body or "").splitlines() if ln.strip()]
    last = lines[-1] if lines else ""
    if m := RECORD_FOOTER.fullmatch(last):
        return {"kind": "record", "ruling": int(m[1]), "lanes": m[2].split(","), "packages": m[3].split(",")}  # fmt: skip
    if m := POINTER_FOOTER.fullmatch(last):
        return {"kind": "pointer", "ruling": int(m[1]), "lane": m[2]}
    if FOOTER_START.match(last):
        return {"kind": "malformed", "line": last}
    return None


def records_for(me: str, binding: list[dict], owner: list[dict]) -> list[str]:
    """``for you:`` per live ``BINDING NOW`` record whose footer names me or ``all`` -- map or no map.

    Ruling 177's filter hides a record the ruling map carries; that is right for "what is still
    unplanned" and wrong for "what is addressed to me", so this reading ignores the map. The body
    comes from the snapshot's own #6854 read (``owner_records`` keeps the text, ``binding_now`` the
    48-hour window), joined by comment id: no new call.
    """
    texts = {r["id"]: r.get("text") for r in owner}
    out = []
    for b in binding:
        f = footer(texts.get(b["id"]))
        if f and f["kind"] == "record" and (me in f["lanes"] or "all" in f["lanes"]):
            out.append(f"  for you: ruling {f['ruling']} record {b['id']} -> packages {','.join(f['packages'])}")  # fmt: skip
        elif f and f["kind"] == "malformed":
            out.append(f"  NOTE unparsed uplevel footer on record {b['id']}: {snap.truncate(f['line'], 80)}")  # fmt: skip
    return out


def pointers_for(me: str, comments: list[dict], now) -> list[str]:
    """``for you:`` per owner pointer naming me, posted anywhere in the last 48 hours.

    The same window as a record (``BINDING_LIFE``), read repo-wide in one call -- not "my open PRs
    since my beat": a pointer posted between one digest and the next beat fell outside that window
    for good, and one on a merged, closed or other lane's PR was never read at all. #6854's own
    comments are skipped here; ``records_for`` reads that issue.
    """
    start = now - snap.BINDING_LIFE
    out = []
    for c in sorted(comments, key=lambda c: c.get("created_at") or ""):
        number = snap.issue_number(c)
        if number == snap.OWNER_ISSUE or snap.parse_time(c["created_at"]) <= start:
            continue
        f = footer(c.get("body"))
        if f and f["kind"] == "pointer" and f["lane"] == me:
            out.append(f"  for you: owner pointer on #{number} (ruling {f['ruling']}) comment {c.get('id')}")  # fmt: skip
        elif f and f["kind"] == "malformed":
            out.append(f"  NOTE unparsed uplevel footer on #{number} comment {c.get('id')}: {snap.truncate(f['line'], 80)}")  # fmt: skip
    return out


def my_beat(items, sandbox: str) -> dict | None:
    """My heartbeat row among ``items`` (each with ``agent`` and ``updated_at``): freshest, by identity.

    Matched by AGENT IDENTITY (``agent_key``), not by the string an agent happened to pass:
    ``--sandbox`` arrives as the hostname or as the marker name and BOTH spellings are live on
    #6958 (see ``build``). Freshest, not first: two spellings can collapse to one identity and the
    endpoint is not reliably sorted. The digest and ``--beat`` both call this, so the beat the
    digest prints is the comment the writer edits.
    """
    key = snap.agent_key(sandbox)
    mine = [h for h in items if snap.agent_key(h["agent"]) == key]
    return max(mine, key=lambda h: h["updated_at"]) if mine else None


def plan_text(body: str | None) -> str | None:
    """A review's ``Plan text:`` value, lower-cased, read through its markdown; ``None`` if absent.

    Measured on the live reviews: the line is written ``- **Plan text:** none.`` as often as
    ``Plan text: none``, so a ``startswith("Plan text:")`` scan finds it on none of them, and the
    value carries backticks, bold and a closing period that are not part of it. An absent line is
    ``None``, never UR-92's default: that default depends on the diff's paths, which this does not read.
    """
    match = PLAN_TEXT.search(body or "")
    if not match:
        return None
    return match.group(1).replace("`", "").strip(" \t*_").rstrip(".").strip(" \t*_").lower()


def ran_for_real(rollup: list[dict], run_id: int | None) -> bool:
    """Did the gate's run run anything? On a draft every job but the gate is skipped and the gate
    still reports SUCCESS over the skipped legs, so a draft run's green gate armed by ruling 198's
    author merges with no CI at all. A real run has some OTHER check of that same run (matched by
    the run id in its ``detailsUrl``) that concluded SUCCESS -- SKIPPED is not success."""
    for c in rollup:
        if (c.get("name") or c.get("context")) == snap.GATE_CHECK:
            continue
        m = snap.RUN_ID.search(c.get("detailsUrl") or c.get("targetUrl") or "")
        if m and run_id is not None and int(m.group(1)) == run_id:
            if (c.get("conclusion") or "").upper() == "SUCCESS":
                return True
    return False


def at_head(s: snap.Snapshot, p: dict, review: dict) -> tuple[bool | None, str]:
    """Is ``review`` a review of PR ``p``'s head, read as the coordinator reads it?

    The newest approval is ``Snapshot.judge``'s own verdict on ``p`` (its ``own_diff`` carry). Any
    other review goes through the same three arms ``judge`` has: the sha it names is the head
    (identity), names no sha (undecided), or names another rev, whose UR-106 own-diff hash either
    carries to the head or not (``Snapshot._own_diff``, the same reads). ``None`` with the reason
    is "the judge cannot decide", the one case the caller falls back to dates for.
    """
    approval = p.get("approval") or {}
    if review.get("id") == approval.get("id"):
        own = p.get("own_diff") or {}
        if own.get("carry") is None:
            return None, p.get("verdict_reason") or own.get("error") or "the carry is unread"
        return own["carry"], ""
    sha = snap.approval_sha(review.get("body") or "")
    if not sha:
        return None, "the review names no sha"
    if p["head"].startswith(sha):
        return True, ""
    probe = {"number": p["number"], "head": p["head"], "errors": p["errors"]}
    s._own_diff(probe, sha, judged_first=True)
    own = probe["own_diff"]
    return own["carry"], ("" if own["carry"] is not None else own.get("error") or "the carry is unread")  # fmt: skip


def review_marker(s: snap.Snapshot, p: dict, reviews: list[dict], head_at: Callable) -> str:
    """Ruling 198's marker for one of MY ready PRs, from its review comments (REVIEWS_JQ's read).

    The reviews are judged exactly as the coordinator's tick and merge audit judge them
    (``Snapshot.judge``, then ``at_head`` for a newest review that is not the newest approval), so
    a marker cannot ask for what the audit then refuses. Only when the judge cannot decide -- the
    review names no sha, or a rev's diff is unread -- is "for this head" read off the head commit's
    COMMITTED date (``head_at``, read lazily: a decided PR pays no date read); an ``arm auto-merge``
    decided that way says so. ``needs your review``: CI at the head has finished and the newest
    review is not for this head. ``arm auto-merge``: the newest review is for this head, approves
    (``is_approval`` on its first line) with ``Plan text: none``, the gate is green from a real
    (non-draft) run, auto-merge is off and there is no ``owner`` label -- an owner-tier PR waits
    for the owner's record, and any other ``Plan text:`` is the author's call, never this marker's.
    """
    s.judge(p, reviews, judged_first=True)  # sorts `reviews` oldest first, as the audit does
    done = p["gate"] in GATE_DONE
    if not reviews:
        return " — needs your review" if done else ""
    newest = reviews[-1]
    here, why = at_head(s, p, newest)
    if here is None:
        when = head_at()
        if when is None:
            return " — review unread"
        here = snap.parse_time(newest["created_at"]) > when
    if not here:
        return " — needs your review" if done else ""
    if (
        snap.is_approval(snap.first_line(newest["body"]))
        and plan_text(newest["body"]) == "none"
        and p["gate"] == "SUCCESS"
        and ran_for_real(getattr(s, "rollups", {}).get(p["number"], []), p.get("gate_run"))
        and not p.get("armed")
        and "owner" not in p["labels"]
    ):
        return " — arm auto-merge" + (f" (by date: {why})" if why else "")
    return ""


def raises_urgent(record: dict, now) -> bool:
    """A live UR-162 raise on #6854 -- a RAISE, not a close.

    Measured live: closes begin ``**URGENT PATH closed — coordinator stale`` and share the first
    eleven characters with a raise, so a prefix test reads a close as a live raise and stays silent
    while the coordinator is stale with no raise on record.
    """
    head = snap.undecorated(snap.first_line(record.get("text")))
    return (
        head.startswith("URGENT PATH")
        and not head.startswith("URGENT PATH closed")
        and (now - snap.parse_time(record["created_at"])) <= URGENT_LIFE
    )


def uncarried(items: list[dict], maptext: str) -> list[str]:
    """Ruling 177: a live record whose ruling number AND comment id both miss the map's rows."""
    out = []
    for b in items:
        num = re.search(r"ruling (\d+)", b["first_line"])
        # Only a `| 188 |` row means the map plans for it: the file quotes ruling numbers in prose
        # too, and a prose mention would otherwise read as carriage and hide a live ruling.
        if not (
            (num and re.search(rf"^\|\s*{num[1]}\s*\|", maptext, re.M)) or str(b["id"]) in maptext
        ):
            out.append(f"  BINDING NOW id={b['id']} not in the ruling map: {b['first_line']}")  # fmt: skip
    return out


def disk(df: str | None, mounts: Sequence[str] = MOUNTS) -> list[str]:
    """UR-180's two mounts; above 90% point at its cleanup ORDER, never a routine full prune.

    A mount the answer does not carry is named as unread rather than dropped: an absent line reads
    as "no disk problem" to a lane that does not know the line was never there.
    """
    rows = {}
    for row in (df or "").splitlines()[1:]:
        cols = row.split()
        if len(cols) >= 5 and cols[4].endswith("%"):
            rows[cols[-1]] = cols[4]
    out = []
    for mount in mounts:
        use = rows.get(mount)
        if use is None:
            out.append(f"  disk {mount} unread (not in df's answer)")
            continue
        over = int(use.rstrip("%")) > 90
        out.append(
            f"  disk {mount} {use}" + (" — over 90%: UR-180's cleanup order" if over else "")
        )
    return out  # fmt: skip


def queue_entries(column: str) -> list[str]:
    """The queue tokens of a roster cell, read as ENTRIES -- not as every backticked word.

    The column is a comma/semicolon-separated list where each entry is a token plus prose, and prose
    legitimately backticks other packages: ops-b's `F2.3` row says "after `[r157]`'s runner is ready
    for the owner" (measured on the live digest, which then reported [r157] held twice), and
    heavy-b's row says "`B2.3` once `O2.4` passes". A ``findall`` over the whole cell turns both of
    those references into queue slots -- and a reference that becomes a queue entry is a package the
    digest will OFFER TO CLAIM, including one that belongs to another lane. So: split on top-level
    separators only (a comma inside `(OP-3, after ...)` separates prose, not entries), then take the
    FIRST token of each entry, because the prose that follows it can name anything.
    """
    entries, depth, cur = [], 0, ""
    for ch in column:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if ch in ",;" and depth == 0:
            entries.append(cur)
            cur = ""
            continue
        cur += ch
    entries.append(cur)
    out = []
    for entry in entries:
        # LEADING token only (measured: every real entry in main's roster starts with its token). An
        # entry whose backtick appears mid-prose is routing prose -- "`B2.3` once `O2.4` passes" and
        # "then assigned `heavy` PRs" -- and skipping it can only OMIT a slot, never INVENT one.
        # That asymmetry is the point: an invented slot gets OFFERED for claim, another lane's work.
        if m := QUEUE_TOKEN.match(entry):
            out.append(m.group(1))
    return out


def held_claims(packages: str, mine: list[dict]) -> list[str]:
    """Every package in MY lane's file that I already hold -- the open claims UR-52 counts.

    UR-52 lets an agent claim only "on any tick where it has no open package", so an open package is
    what closes the claim leg. The scan walks the **package file**, not the roster queue: the two
    sources disagree in both directions and a hold the queue does not name is still a hold. Measured
    on ``main``: ops-a holds ``[r162]`` (#7114 open, titled ``[r162]``, and ``ops.md``'s own field
    reads ``**PR:** #7114 (open)``) while its roster column at ``roles/lane.md:23`` carries no
    ``[r162]`` token at all -- so a queue-driven scan answered "no holds" and the digest offered
    ``next claimable: r164a`` mid-flight, the exact queue-jump UR-52 forbids. Gating on the queue was
    the defect: an index built from one file used to answer a question the other file defines.
    ``next_claimable`` stays queue-ordered -- a FRESH claim must be a queue slot -- only eligibility
    widens to file-wide holds. Cannot over-suppress across a lane's cells, because ``mine`` is
    already branch-filtered upstream.

    Two independent hold readings, because either can be the only live one: the ``[<pkg>]`` **title
    token** of an open PR (authoritative; a ``[UR-nn]`` defect fix -- UR-48, no package number --
    titles no package and gates nothing), or the block's own ``**PR:**`` number naming a PR of mine.
    A ``**PR:** none yet`` block is never a field-hold even when its prose cites a ``#`` issue:
    ``[r172]`` reads ``none yet. (ruling 172; issue #7102)`` on main, and an issue reference is not
    a claim, so ``NONE_YET`` is honoured here exactly as ``next_claimable`` honours it.
    """
    numbers = {str(p.get("number")) for p in mine}
    titles = " ".join(p.get("title", "") for p in mine)
    held = []
    for block in packages.split("### ")[1:]:
        m = BLOCK.match(block)
        if not m:
            continue
        token = m.group(1)
        if f"[{token}]" in titles:
            held.append(token)
            continue
        field = PKG_FIELD.search(block)
        if field and NONE_YET.match(field.group(1).lstrip()):
            continue
        named = PR_NUMBER.search(field.group(1)) if field else None
        if named and named.group(1) in numbers:
            held.append(token)
    return held


def next_claimable(packages: str, queue: list[str], mine: list[dict]) -> str | None:
    """First package on MY roster queue that carries no PR and that no open PR of mine titles.

    Three readings the file's shapes force. (1) The queue, not the file: ``ops.md`` carries ops-a's
    ``[r164a]`` with ``**PR:** none yet`` ahead of mine, so a scan of the file offers another cell's
    package. (2) The title, not the row: the ``**PR:**`` field is coordinator-owned and lags the
    claim, so the package would be offered to me while I am mid-flight on it. (3) Only on a tick
    with no open package, which ``held_claims`` enforces in ``build`` -- a claimable line printed
    beside an open package is an invitation to queue-jump, which UR-52 forbids.
    """
    titles = " ".join(p.get("title", "") for p in mine)
    blocks = {m.group(1): b for b in packages.split("### ")[1:] if (m := BLOCK.match(b))}
    for token in queue:
        block = blocks.get(token)
        if block is None:
            continue  # a queue entry that is not a package block here (an F2.3 batch, a trigger)
        field = PKG_FIELD.search(block)
        if field and NONE_YET.match(field.group(1).lstrip()) and token not in titles:
            return token
    return None


def behind(run, repo: str, number: int) -> str:
    """Commits ``origin/main`` has that this head lacks -- the number a rebase decision needs.

    The reversed range (``head..origin/main``) counts the head's own work ahead of main, which is a
    different number and the wrong one here.
    """
    return run(
        ["git", "rev-list", "--count", f"refs/remotes/origin/pr/{number}..origin/main"]
    ).strip()


# --- rendering ------------------------------------------------------------------------------


def build(
    run: Callable[[Sequence[str]], str], clock: Callable[[], object], repo: str, sandbox: str
) -> list[str]:
    """The tick's readings, in tick order, from one runner and one clock. Read-only."""
    s = LaneSnap(repo, run, clock, None)
    data = s.build()
    extra: list[str] = []

    def call(cmd: Sequence[str], tag: str) -> str | None:
        try:
            return run(cmd)
        except Exception as exc:  # reported in its section, never a silent empty one
            extra.append(f"  ERROR {tag}: {snap.error_text(exc)}")
            return None

    def api(path: str, tag: str) -> list:
        return snap.parse_json_stream(call(["gh", "api", path, "--paginate"], tag) or "")

    def show(path: str, tag: str) -> str:
        return call(["git", "show", path], tag) or ""

    def packages(lane: str) -> str:
        """This lane's package file, or ``""`` when the lane has none. A lane with no package file on ``main``
        is a fact about the programme, not a failed read, and prints a NOTE rather than an ERROR.

        ``main`` carries package files for backend/docs/frontend/ops only (measured: 4 files), and
        the roster's coordinator, heavy-a, heavy-b and operator rows have work that is never
        packaged -- so this case is one of the two roles box 3 points here. Existence is asked
        positively, by ``ls-tree``'s answer, because a failing ``git show`` cannot tell "no package
        file for this lane" apart from "the read broke": both arrive as a non-zero exit, and
        reading git's stderr to separate them makes the classification depend on the wording of an
        error message. A NOTE is safe either way -- the lane's next package comes from its roster
        row, which is the same answer the file would have given.
        """
        ref = PKGS.format(lane)
        try:
            # `:/` makes the pathspec top-level-relative, so the answer does not depend on which
            # directory the tick happened to run from (git show's `<rev>:<path>` form already is).
            listed = run(["git", "ls-tree", "origin/main", "--", f":/{ref.partition(':')[2]}"])
            if not listed.strip():
                extra.append(f"  NOTE no package file for lane {lane}: next claimable not read")
                return ""
            return run(["git", "show", ref])
        except Exception as exc:
            extra.append(f"  ERROR packages: {snap.error_text(exc)}")
            return ""

    try:
        # Read directly, not through call(): this is the one failure that ends the report, and a
        # call() that already logged it would put one cause in the report twice under two names.
        ids = identities(run(["git", "show", ROSTER]), sandbox)
    except Exception as exc:  # without the lane nothing downstream can be keyed
        return [f"ERROR identities: {snap.error_text(exc)}"]
    now = snap.parse_time(data["cursor"]["now"])
    beats = {h["agent"]: h for h in data["heartbeats"].get("items", [])}
    # Matched by AGENT IDENTITY, not by the string an agent happened to pass. The roster row lookup
    # above already does this deliberately (`.endswith`), because `--sandbox` arrives either as the
    # hostname (`agent-uplevel-ops-b`, what `$SANDBOX_NAME`/`hostname` give and so what the role
    # docs' `<your-sandbox>` resolves to) or as the marker name (`uplevel-ops-b`), and BOTH spellings
    # are live on #6958 -- measured: `uplevel-ops-a`, `uplevel-ops-b` and `uplevel-operator` beat
    # bare while `agent-uplevel-backend`, `-frontend`, `-docs`, `-coordinator` and `-heavy-a/b` beat
    # prefixed. A plain `beats.get(sandbox)` therefore missed a lane's OWN beat whenever the two
    # spellings disagreed: the digest printed `ERROR heartbeats` AND, worse, fell through to the
    # coordinator's cursor as the comment window, silently re-labelling step 4's `Nc/Nr since beat`.
    # `agent_key` is the snapshot's existing normalization -- the same one box 2's signed-activity
    # rule uses -- so the two readings cannot disagree about which agent an argument names.
    # Freshest, not first: an agent is supposed to keep ONE beat (the role docs edit it in place) but
    # the marker spelling is not stable, so two rows can collapse to one identity -- and the
    # heartbeat endpoint is not reliably sorted, so "first match" would be an arbitrary pick.
    mybeat = my_beat(beats.values(), sandbox)
    # Same tie-break for the coordinator's row, whose age is the UR-162 trigger: a stale duplicate
    # picked first would raise a URGENT PATH that is not owed. The `.endswith` SELECTOR is unchanged,
    # so this only chooses among rows it already found -- it cannot lose the row it finds today.
    coord_beats = [h for a, h in beats.items() if a.endswith("coordinator")]
    coord = max(coord_beats, key=lambda h: h["updated_at"]) if coord_beats else None
    owner = data.get("owner_records", {}).get("items", [])
    urgent = [r for r in owner if raises_urgent(r, now)]
    who = f"{ids['lane']}-{ids['cell']}" if ids["cell"] else ids["lane"]
    out = [f"# lane tick {sandbox} {data['cursor']['now']} agent={who}"]
    # Ruling 197: what is addressed to me, gathered through the tick and printed FIRST (right under
    # the title line), because the role's step 1 acts on these before anything else it reads.
    me = footer_name(sandbox)
    for_you = records_for(me, data["binding_now"].get("items", []), owner)
    out.append(
        f"  heartbeat id={mybeat['id']} age {mybeat['age_min']}m {snap.truncate(mybeat['head'], 70)}"
        if mybeat
        else f"  ERROR heartbeats: no beat for {sandbox} on #{snap.HEARTBEATS_ISSUE}"
    )
    since = mybeat["updated_at"] if mybeat else data["cursor"].get("cursor", "")
    if coord:
        flag = " — UR-162: post one URGENT PATH on #6854" if coord["stale"] and not urgent else ""
        rested = f" (a live URGENT PATH already on record: #{urgent[-1]['id']})" if coord["stale"] and urgent else ""  # fmt: skip
        out.append(f"  coordinator age {coord['age_min']}m{rested}{flag}")
    out += disk(call(["df", "-h", *MOUNTS], "disk"))
    pkgs, maptext = packages(ids["lane"]), show(MAP, "ruling map")
    out += uncarried(data["binding_now"].get("items", []), maptext)

    cmd = ["gh", "pr", "list", "--repo", repo, "--state", "open", "--limit", "300", "--json", HEADJ]  # fmt: skip
    listed = json.loads(call(cmd, "heads") or "[]")
    heads = {p["number"]: p for p in listed}
    branches = set((call(["git", "branch", "--format=%(refname:short)"], "branches") or "").split())

    def gate(p: dict) -> str:
        """The gate's verdict, named by its in-flight jobs when it is still running."""
        if p["gate"] != "IN_PROGRESS" or not p.get("gate_run"):
            return p["gate"]
        rows = api(f"repos/{repo}/actions/runs/{p['gate_run']}/jobs?per_page=100", "jobs")
        jobs = rows[0].get("jobs", []) if rows and isinstance(rows[0], dict) else []
        # The gate is a leg of its OWN run, so it is never the thing a lane is waiting on.
        running = ",".join(
            j.get("name", "?")
            for j in jobs
            if j.get("status") != "completed" and j.get("name") != snap.GATE_CHECK
        )
        return f"IN_PROGRESS({snap.truncate(running, 60)})" if running else p["gate"]

    def row(p: dict, tail: str = "") -> str:
        errs = "".join(f" ERROR {e}" for e in p.get("errors", []))
        return (
            f"  #{p['number']} {snap.truncate(p['title'], 40)} head={p['head'][:9]}"
            f" {p['merge_state']} gate={gate(p)}{tail}{errs}"
        )

    items = data["prs"].get("items", [])
    # Ownership by BRANCH, not label or author: two-cell lanes carry no cell row on some of their
    # own PRs and every PR has the owner's login behind it (UR-168). Ruling 198 ended cross-lane
    # review -- each PR's one review is its author's UR-89 subagent, and no PR carries a
    # `review:<lane>` label -- so the digest's PR section is my own PRs and nothing else.
    mine = [p for p in items if heads.get(p["number"], {}).get("headRefName") in branches]

    def marker(p: dict) -> str:
        """Ruling 198's ``needs your review`` / ``arm auto-merge`` for a ready PR of mine. Its reads
        go through the runner: the snapshot's own verdict read (REVIEWS_JQ, the call ``_review``
        makes), the UR-106 own-diff reads ``judge`` makes for an approval of another rev, and --
        only when the judge cannot decide -- the head commit's committed date from the head ref the
        snapshot fetched. A failed read prints ``review unread`` on the row and an ERROR line, never
        a missing marker that would read as "nothing to do"."""
        if p["draft"]:
            return ""  # a draft is neither reviewed nor armed (ruling 198: skipped jobs pass)
        n = p["number"]
        try:
            path = f"repos/{repo}/issues/{n}/comments?per_page=100"
            reviews = s.gh_paginated(path, "--jq", snap.REVIEWS_JQ)
        except Exception as exc:
            extra.append(f"  ERROR review comments #{n}: {snap.error_text(exc)}")
            return " — review unread"

        def head_at():
            try:
                return snap.parse_time(run(["git", "log", "-1", "--format=%cI", p["head"]]))
            except Exception as exc:
                extra.append(f"  ERROR head date #{n}: {snap.error_text(exc)}")
                return None

        return review_marker(s, p, reviews, head_at)

    out.append(f"== mine ({len(mine)})")
    for p in mine:
        tail = " DIRTY" if p["merge_state"] == "DIRTY" else ""
        try:
            tail += f" behind {behind(run, repo, p['number'])}"
        except Exception as exc:
            extra.append(f"  ERROR behind #{p['number']}: {snap.error_text(exc)}")
            tail += " behind ?"
        cmts = api(f"repos/{repo}/issues/{p['number']}/comments?since={since}&per_page=100", "comments")  # fmt: skip
        revs = [
            r
            for r in api(f"repos/{repo}/pulls/{p['number']}/reviews?per_page=100", "reviews")
            if (r.get("submitted_at") or r.get("created_at") or "") >= since
        ]
        out.append(row(p, f"{tail} {len(cmts)}c/{len(revs)}r since beat{marker(p)}"))
    # Ruling 197's pointers: one repo-wide read over the records' 48-hour window. GitHub's `since`
    # bounds it by update time; `pointers_for` bounds it by posting time, as `_binding_now` does.
    window = snap.iso(now - snap.BINDING_LIFE)
    raw = call(["gh", "api", f"repos/{repo}/issues/comments?since={window}&per_page=100", "--paginate"], "pointers")  # fmt: skip
    if raw is not None:
        for_you += pointers_for(me, snap.parse_json_stream(raw), now)
    # UR-52's precondition, printed: an agent holding an open package is not claim-eligible, and a
    # `next claimable` line beside a held package invites the queue-jump the rule forbids. The gate
    # reads the whole lane file, not the queue column, because a package the roster never lists is
    # still an open package ([r162] on ops-a's row is that shape). Silence would be worse than either
    # line -- it could mean "nothing claimable" or "not eligible" -- so the digest says which it read.
    if held := held_claims(pkgs, mine):
        names = ", ".join(f"[{t}]" for t in held)
        out.append(
            f"  holding open claim: {names} (UR-52: nothing to claim while a package is open)"
        )
    elif nxt := next_claimable(pkgs, ids["queue"], mine):
        out.append(f"  next claimable: {nxt}")
    for name in ("cursor", "comments", "binding_now", "main", "heartbeats", "prs"):
        out += [f"  ERROR {name}: {e}" for e in data.get(name, {}).get("errors", [])]
    out += extra
    out[1:1] = for_you  # first under the title; counted by the cap below like every other line
    if (
        len(out) > CAP_LINES
    ):  # the cap reports, it does not cut: status_draft's over_limit does the same
        out.append(f"  NOTE {len(out) - CAP_LINES} lines over this tool's {CAP_LINES}-line cap")
    return out


def beat_body(sandbox: str, text: str) -> str:
    """The whole heartbeat: the marker line the TOOL writes, then the agent's own line(s)."""
    return f"{snap.HEARTBEAT_PREFIX}{sandbox} -->\n{text}"


def beat(
    run: Callable[[Sequence[str]], str],
    clock: Callable[[], object],
    repo: str,
    sandbox: str,
    text: str,
) -> tuple[int, str]:
    """Write my heartbeat on #6958 (ruling 197) and return ``(exit code, the one line to print)``.

    Hand-edited markers drifted three times, so the marker line is written here from ``--sandbox``
    and ``text`` is only what follows it. Refused before any read (exit 2): a body over UR-155's
    600 characters, and a ``text`` that carries a marker of its own (the role docs once said to
    PATCH "the two lines", and passing both here would put two markers in one beat). My comment is
    found by the snapshot's own #6958 read and ``my_beat``'s identity rule, so the beat the digest
    prints is the one this edits; with none, one is posted. A failed read writes nothing (exit 1):
    "no beat found" from a read that did not happen would post a duplicate row. The coordinator is
    refused outright: its beat carries the ``read-through:`` cursor every tick reads from, which a
    two-line lane beat written over it would erase (``roles/coordinator.md`` owns that comment).
    """
    body = beat_body(sandbox, text)
    if footer_name(sandbox) == "coordinator":
        return 2, "refused: the coordinator's beat carries its read-through: cursor; write it as roles/coordinator.md says"  # fmt: skip
    if snap.HEARTBEAT_PREFIX in text:
        return 2, "refused: --beat takes the line(s) after the marker; the tool writes the marker"
    if len(body) > BEAT_CAP:
        return 2, f"refused: the beat is {len(body)} characters, over UR-155's {BEAT_CAP}"
    raw = LaneSnap(repo, run, clock, None)._heartbeat_comments()
    if isinstance(raw, Exception):
        return 1, f"ERROR heartbeats: {snap.error_text(raw)} (nothing written)"
    rows = [
        {"agent": agent, "id": c.get("id"), "updated_at": c.get("updated_at") or ""}
        for c in raw
        if (agent := snap.heartbeat_agent(c.get("body"))) is not None
    ]
    mine = my_beat(rows, sandbox)
    try:
        if mine:
            path, verb = f"repos/{repo}/issues/comments/{mine['id']}", "PATCH"
        else:
            path, verb = f"repos/{repo}/issues/{snap.HEARTBEATS_ISSUE}/comments", "POST"
        answer = run(["gh", "api", "-X", verb, path, "-f", f"body={body}"])
    except Exception as exc:
        return 1, f"ERROR beat: {snap.error_text(exc)}"
    if mine:
        return 0, f"beat written: comment {mine['id']} on #{snap.HEARTBEATS_ISSUE} ({len(body)}/{BEAT_CAP} chars)"  # fmt: skip
    try:
        new_id = json.loads(answer or "{}").get("id", "?")
    except ValueError:
        new_id = "?"
    return 0, f"beat posted: new comment {new_id} on #{snap.HEARTBEATS_ISSUE} ({len(body)}/{BEAT_CAP} chars)"  # fmt: skip


def main(
    argv: Sequence[str] | None = None,
    run: Callable[[Sequence[str]], str] = snap.run_command,
    clock: Callable[[], object] = snap.utc_now,
) -> int:
    ap = argparse.ArgumentParser(description="the lane tick's readings in one read-only call")
    ap.add_argument("--sandbox", required=True)
    ap.add_argument("--repo", default=snap.DEFAULT_REPO, type=snap._repo_arg)
    ap.add_argument("--beat", metavar="TEXT", help="write my heartbeat (line 2 on) instead of reading")  # fmt: skip
    a = ap.parse_args(argv)
    if a.beat is not None:
        code, line = beat(run, clock, a.repo, a.sandbox, a.beat)
        print(line, file=sys.stderr if code else sys.stdout)
        return code
    print("\n".join(build(run, clock, a.repo, a.sandbox)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
