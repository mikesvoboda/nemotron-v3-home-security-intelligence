#!/usr/bin/env python3
"""The coordinator's tick reading in one call (ruling 152; docs/uplevel/roles/coordinator.md).

    uv run python scripts/uplevel/coordinator_snapshot.py [--repo OWNER/REPO] [--since UTC] [--json]

Run it from a checkout whose ``origin`` is the repository: it runs ``git fetch origin`` itself.
It reads GitHub through ``gh`` and the tree through ``git``, and prints one compact report:

1. cursor     - the ``read-through:`` line of the coordinator heartbeat on #6958 (absent: now-2h),
                and ``now``, the time of the comments call, which the tick writes back last;
2. comments   - every comment updated since the cursor, repo-wide; heartbeat and status-comment
                markers counted, not listed; ``BINDING NOW`` (UR-40) and ``URGENT PATH`` (UR-168)
                flagged; plus the live ``BINDING NOW`` records on #6854 from the last 48 h;
3. prs        - each open PR: head, merge-base, mergeStateStatus, ``CI Gate`` at the head, the
                newest ``Review: approve`` comment's sha against the head (UR-106), and the
                UR-106 own-diff hash at the head and at the approved head with ``carry:``;
4. merge state  - per non-draft PR: whether it is behind `main` (its `base=` is not main's tip),
                and whether it shows the in-flight sign of `roles/coordinator.md` "Merging a PR"
                step 1 (base at the tip, the gate not finished, and the approval carries),
5. main       - tip, CI (UR-111), Deploy, Nightly Full Gate and Flaky Test Detection (UR-116);
6. heartbeats - every ``<!-- heartbeat:`` comment on #6958, its age and ``paused`` (UR-38, UR-160),
                flagged when older than 20 minutes (UR-162);
7. auto-merge - each armed PR sorted ok / to-disable / unknown (UR-108: an armed head must be the
                approved head or a UR-106 carry of it, and an unread carry is never a reason to
                disable);
8. merged     - each PR merged since the cursor: the verdict on whether its landed head (the merge
                commit's second parent) is the approved head or a carry, what bars it (UR-94), and
                a pre-filled UR-29 merge comment with its gaps marked ``unread``.

It never writes to GitHub. A failed ``gh`` or ``git`` call prints ``ERROR <section>: <message>``
in its section and the report goes on; the exit code is 0 unless the arguments are invalid.
Every subprocess call goes through one ``Runner`` so the tests replace it without a network.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

DEFAULT_REPO = "mikesvoboda/nemotron-v3-home-security-intelligence"
HEARTBEATS_ISSUE = 6958
OWNER_ISSUE = 6854
COORDINATOR_MARKER = "<!-- heartbeat:agent-uplevel-coordinator -->"
HEARTBEAT_PREFIX = "<!-- heartbeat:"
STATUS_MARKER = "<!-- status:uplevel-coordinator -->"
GATE_CHECK = "CI Gate (Required Checks)"
# `gh pr list --json statusCheckRollup` returns at most this many check runs per PR. Measured
# 2026-10-13: #7070 has 129 and the batch hands back exactly 100, with both `CI Gate` rows past
# the cut, which is why §3 printed gate=absent for a PR with a green gate. A batch of exactly
# this length is known-truncated, so it is not evidence about the gate at all.
LIST_ROLLUP_CAP = 100
# The merged-PR scan is a client-side filter: REST /pulls has no ``since`` param. It is bounded by
# an exit on ``updated_at`` (sound: a PR merged after the cursor was updated after it, so every
# merge still in the window is on the first page of a ``sort=updated`` scan) and by one page. The
# report says ``scanned:`` and sets ``possibly_more`` so "no merges" cannot read as "looked".
SCAN_PAGE = 100
DEFAULT_LOOKBACK = timedelta(hours=2)
BINDING_LIFE = timedelta(hours=48)
STALE_HEARTBEAT_MIN = 20
# Ruling 239 ([r239]): the coordinator's own 30-minute loop can leave its heartbeat about 90
# minutes old (a tick up to 60 plus up to 30 until the next fire), so UR-162's trigger is keyed
# by the agent's identity -- the coordinator raises only past 90; every other heartbeat keeps 20.
COORDINATOR_STALE_HEARTBEAT_MIN = 90
# Ruling 245's interval table (UR-36), three of each agent's own intervals per UR-38: heavy runs
# a 15-minute loop, every other agent 30 ([r193]'s watcher is merged, so lanes are on 30).
LANE_LOOP_MIN = 30
HEAVY_LOOP_MIN = 15
STALL_MULTIPLIER = 3
FIRST_LINE_MAX = 160
RED_CONCLUSIONS = frozenset({"failure", "timed_out", "startup_failure"})

READ_THROUGH = re.compile(
    r"read-through:\s*`?([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]+(?:Z|[+-][0-9:]+)?)"
)
HEX_TICKED = re.compile(r"`([0-9a-f]{7,40})`")
HEX_BARE = re.compile(r"\b([0-9a-f]{7,40})\b")
HEAD_LINE = re.compile(r"^[\s*_>-]*Head(?: reviewed)?:", re.IGNORECASE)
LEAD_DECORATION = "*_ >#"
# A heartbeat's status is one field of a middot-separated line (`agent · 19:07Z · paused · why`),
# and the field can be markdown-decorated (`**paused**`, `` `paused` ``).
HEARTBEAT_FIELD_SEP = "·"
FIELD_DECORATION = "*_ >#`\t "
# A verdict arrives as an issue comment, never as a review object (the APPROVE event 422s on this
# workspace), and its first line is written by hand: `Review: approve` and `Review: **approve[d]**`
# are both a verdict. A literal `startswith("Review: approve")` reads the decorated one as no
# approval at all, which is worse than noise — it reports a live key as STALE and invites a void.
REVIEW_HEADLINE = re.compile(r"^Review:\s*[*>_ `\t]*(approve|approved)\b", re.IGNORECASE)
RUN_ID = re.compile(r"/actions/runs/([0-9]+)(?:/|$)")
# The sed in UR-106's pipeline: `s/^@@ .* @@/@@/`. Byte-level, because sed and sha256sum are.
HUNK_HEADER = re.compile(rb"^@@ .* @@", re.MULTILINE)
# An owner hold in the owner's own voice: UR-45 reserves "RULING" for the owner and UR-40
# reserves "BINDING NOW", so the bar keys on those first-line shapes plus the hold phrase and
# the PR number -- never on the author, which is the same account for everything (memory
# shared-token-pr-ownership-not-author). The coordinator's status comment is excluded upstream
# by its marker, so its "#7106 merged" mention of an open PR cannot bar.
OWNER_VOICE = re.compile(r"^(RULING|BINDING NOW)\b")
OWNER_HOLD = re.compile(r"\bdo not merge\b", re.IGNORECASE)
# A hold recorded in the PR body's Notes, the coordinator's own bookkeeping area: a
# ``Notes: owner:`` line quotes an owner instruction into the PR (the same slot the
# ``Notes: Auto-merge:`` marker occupies, ruling 156). A bare "do not merge" in prose is not
# that shape; the prefix is what marks it as a recorded instruction, not discussion text.
BODY_HOLD = re.compile(
    r"^\s*[-*]?\s*Notes:\s*owner:.*\bdo not merge\b", re.IGNORECASE | re.MULTILINE
)
OWNER_PR_REF = re.compile(r"#([0-9]{3,6})\b")


# The verdict-shape filter, shared by §3's review read and §8's so the two cannot drift on what
# counts as a verdict thread.
REVIEWS_JQ = (
    '[.[] | select(.body | startswith("Review:")) | {id, created_at, user: .user.login, body}]'
)

Runner = Callable[[Sequence[str]], str]
Clock = Callable[[], datetime]


class CommandError(Exception):
    """A gh or git call exited non-zero."""


def run_command(cmd: Sequence[str]) -> str:
    """The real runner: run ``cmd``, return stdout, raise CommandError on a non-zero exit."""
    try:
        proc = subprocess.run(list(cmd), capture_output=True, text=True, check=False, timeout=300)
    except OSError as exc:
        raise CommandError(f"{cmd[0]}: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise CommandError(f"{' '.join(cmd[:3])}: timed out") from exc
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout).strip().splitlines()
        msg = tail[-1] if tail else "no output"
        raise CommandError(f"{' '.join(cmd[:3])} exited {proc.returncode}: {msg}")
    return proc.stdout


def utc_now() -> datetime:
    return datetime.now(UTC)


# --- small helpers -------------------------------------------------------------------------


def parse_time(text: str) -> datetime:
    """Parse an ISO-8601 time; a naive one is taken as UTC."""
    dt = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_json_stream(text: str) -> list[Any]:
    """Parse ``gh api --paginate`` output: one JSON value per page, arrays flattened."""
    decoder = json.JSONDecoder()
    out: list[Any] = []
    i, n = 0, len(text)
    while True:
        while i < n and text[i].isspace():
            i += 1
        if i >= n:
            return out
        value, i = decoder.raw_decode(text, i)
        if isinstance(value, list):
            out.extend(value)
        else:
            out.append(value)


def first_line(body: str | None) -> str:
    return (body or "").lstrip().split("\n", 1)[0].strip()


def truncate(text: str, limit: int = FIRST_LINE_MAX) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def undecorated(line: str) -> str:
    return line.lstrip(LEAD_DECORATION)


def is_approval(line: str) -> re.Match[str] | None:
    """Is this first line a verdict? One predicate, so §3's headline and §3's note cannot disagree."""
    return REVIEW_HEADLINE.match(line)


def is_paused(head: str) -> bool:
    """UR-160's paused flag is the heartbeat's STATUS FIELD, not any mention of the word.

    A substring test over the head lines flagged 2 of 9 live heartbeats that are not paused: the
    coordinator's own row (prose about which lanes are live) and the operator's (prose about who
    stopped whom). §6 prints `[paused]` and the coordinator routes work off it, so a false pause
    silently reroutes a live lane's packages.
    """
    for line in head.splitlines()[1:]:
        for field in line.split(HEARTBEAT_FIELD_SEP):
            if field.strip().strip(FIELD_DECORATION).strip().lower() == "paused":
                return True
    return False


def is_marker(line: str) -> bool:
    return line.startswith(("<!-- heartbeat", STATUS_MARKER))


def heartbeat_agent(body: str | None) -> str | None:
    """The agent a heartbeat comment's marker names (``<!-- heartbeat:<agent> -->``), else ``None``.

    One reading for §6 and for ``lane_tick.py --beat`` (ruling 197), so the row the digest prints
    and the comment the beat writer edits cannot be told apart by two parsers of one marker.
    """
    body = (body or "").lstrip()
    if not body.startswith(HEARTBEAT_PREFIX):
        return None
    return body[len(HEARTBEAT_PREFIX) :].split("-->", 1)[0].strip()


def issue_number(comment: dict[str, Any]) -> int | None:
    url = comment.get("issue_url") or ""
    tail = url.rstrip("/").rsplit("/", 1)[-1]
    return int(tail) if tail.isdigit() else None


# --- signed activity (ruling 178) ------------------------------------------------------------

# Every comment in this programme is posted with the owner's token and every commit is authored
# as `mike svoboda`/`mikesvoboda` (measured on #7125/#7145/#7159/#7163/#7164), so neither an
# author field nor a commit trailer identifies the agent that wrote it. Ruling 178 names what
# does: a ``Reviewer lane: <lane>`` line (a review's lane is on its SECOND line, so it is read
# from the body, not the first line), or the agent's lane/sandbox name leading the first line.
# A PR's labels name who its commits belong to (``lane:<lane>`` plus ``cell:<cell>``/``heavy``).
REVIEW_LANE = re.compile(
    r"^[ \t]*Reviewer lane:[ \t]*([a-z-]+)(?:[ \t]*\(cell[ \t]*([ab])\))?", re.IGNORECASE | re.M
)
# The name leading an agent's own line: every lane and operator beat starts
# ``<sandbox> · <HH:MMZ> · ...`` and every status comment ``<who> · <time> reads``, so the FIRST
# token of the undecorated first line is the writer. A name anywhere else is the subject someone
# else is writing ABOUT -- the live read showed ``URGENT PATH · stalled agent:
# `agent-uplevel-heavy-b``` counted as heavy-b's own activity, refuting with the raise the very
# stall it raises. Position is what tells the writer from the subject.
HEAD_NAME = re.compile(r"^[ \t>*_#`]*([\w.-]+)")


def agent_key(beat_agent: str) -> tuple[str, str | None]:
    """``(lane, cell)`` from a heartbeat's marker name: ``agent-uplevel-ops-b``/``uplevel-ops-b``
    (both spellings are live) -> ``("ops", "b")``; a one-cell lane -> cell ``None``.

    The ``agent-`` prefix is not applied consistently -- ops-a beats as ``uplevel-ops-a`` while
    ops-b beats as ``agent-uplevel-ops-b`` -- so it is stripped before the tail is split.
    """
    name = beat_agent.removeprefix("agent-")
    tail = name.removeprefix("uplevel-")
    lane, _, cell = tail.rpartition("-")
    return (tail, None) if not lane else (lane, cell.lower())


def stall_threshold(beat_agent: str) -> int:
    """Ruling 245's stalled age for ONE agent: three of its own UR-36 intervals (UR-38).

    ``agent_key`` splits the marker's tail, so ``agent-uplevel-heavy-b`` and ``uplevel-heavy-b``
    both read as the heavy family; every other agent -- the fast lanes, the coordinator and the
    operator -- runs the 30-minute loop [r193] put in force. Before [r193] a lane was on 15 and
    stalled at 45; the package's merge order note says whichever of the two merges second sets
    the lanes' row, and [r193] has merged, so the table lands at its post-[r193] values.
    """
    lane, _ = agent_key(beat_agent)
    loop = HEAVY_LOOP_MIN if lane == "heavy" else LANE_LOOP_MIN
    return loop * STALL_MULTIPLIER


def stale_threshold(beat_agent: str) -> int:
    """UR-162's staleness threshold for ONE heartbeat row, keyed by the agent's identity.

    Ruling 239 ([r239]): the coordinator's heartbeat raises only past 90 minutes (its 30-minute
    loop can leave the beat about that old); every other agent keeps 20. Keyed on the marker
    name's tail, not the raw string -- ``uplevel-coordinator`` and ``agent-uplevel-coordinator``
    are both live spellings -- and matched with the same ``endswith`` the digest's tie-break
    uses, so the two readers cannot disagree about who is the coordinator.
    """
    return (
        COORDINATOR_STALE_HEARTBEAT_MIN
        if beat_agent.removeprefix("agent-").endswith("coordinator")
        else STALE_HEARTBEAT_MIN
    )


def head_name(line: str) -> str | None:
    """The first token of an undecorated first line -- the writer, per the role docs' line shape."""
    match = HEAD_NAME.match(undecorated(line))
    return match.group(1) if match else None


def review_lane(body: str) -> tuple[str, str | None] | None:
    """The ``(lane, cell)`` a review's body declares, or ``None`` if it declares none.

    The declared lane is normalized through ``agent_key`` so ``heavy-a`` and ``heavy (cell A)``
    and ``ops`` all land in the same shape as the heartbeat marker's name.
    """
    if not (match := REVIEW_LANE.search(body or "")):
        return None
    lane, cell = agent_key(match.group(1).lower())
    return (lane, (match.group(2) or "").lower() or cell)


def signs_agent(comment: dict[str, Any], lane: str, cell: str | None) -> str | None:
    """``"self"`` if the comment is signed by exactly this agent, ``"lane"`` if it names the lane
    but leaves a two-cell lane's cell open (so it cannot refute one cell's stall), else ``None``.

    Reads the two forms ruling 178 lists, from data a comment already carries: its ``review_lane``
    (a review, whose lane may sit on line 2) and its leading ``head_name`` (the beat/lead line).
    """
    if named := comment.get("review_lane"):
        named_lane, named_cell = named
        if named_lane != lane.lower():
            return None
        if cell is None or named_cell == cell:
            return "self"
        if named_cell in ("a", "b"):
            # It names THIS lane and the OTHER cell: it signs that agent, not this one. Reading
            # it lane-wide would refute a stalled ops-a with ops-b's review -- the exact false
            # negative ruling 178 exists to prevent.
            return None
        return "lane"
    head = (comment.get("head_name") or "").lower()
    if not head:
        return None
    full = f"{lane}{f'-{cell}' if cell else ''}".lower()
    # The role docs put an agent's name in the author position: the FIRST token of the
    # undecorated first line. A bare name elsewhere in a line is the SUBJECT of someone else's
    # comment -- a coordinator's `URGENT PATH · stalled agent: agent-uplevel-heavy-b` naming the
    # agent it raises about -- and counting it as the agent's own activity would refute the very
    # stall it raises (measured live: heavy-b's row printed the coordinator's raise as its own).
    if head in {f"agent-uplevel-{full}", f"uplevel-{full}", full}:
        return "self"
    if cell and head == lane.lower():
        return "lane"  # the lane's own spelling leads the line: this lane, but not this cell
    return None


def owner_of_pr(labels: list[str]) -> tuple[str, str | None, bool] | None:
    """``(lane, cell, named_exactly)`` for the agent a PR belongs to, or ``None`` if unlabeled.

    `rules.md:92-93`: a claim PR carries ``lane:<lane>`` and, where they apply, ``cell:<cell>``
    and ``heavy``; a ``heavy`` PR labelled ``cell:heavy-b`` is heavy-b's, every other heavy PR
    heavy-a's. Every non-heavy lane has one agent except ops, which has two -- so a ``lane:ops``
    PR with no ``cell:`` row belongs to one of two agents and comes back ``named_exactly=False``
    (#7159 is that case). Printing it under either cell would tell the coordinator the other
    cell's agent pushed it; it is listed beside both instead.
    """
    cells = {v for lbl in labels if (v := lbl.removeprefix("cell:")) != lbl}
    lane = next((v for lbl in labels if (v := lbl.removeprefix("lane:")) != lbl), None)
    if "heavy" in labels:
        return ("heavy", "b" if "heavy-b" in cells else "a", True)
    if lane is None:
        return None
    if lane == "ops":
        cell = next((c for c in cells if c in ("a", "b")), None)
        return (lane, cell, cell is not None)
    return (lane, None, True)


def error_text(exc: Exception) -> str:
    return str(exc) if isinstance(exc, CommandError) else f"{type(exc).__name__}: {exc}"


def ur106_diff_hash(diff: str) -> str:
    """The UR-106 hash of a PR's own diff, as ``roles/coordinator.md`` §Merging a PR step 2
    defines it: drop the ``index`` lines, blank every hunk header, hash what is left.

    The filter is written at the byte level because the pipeline it stands in for is: ``grep``
    and ``sed`` act on bytes and ``sha256sum`` hashes bytes, so re-encoding the text here would
    make the hash depend on an encoding choice. It matches the pipeline exactly -- a whole
    ``index `` line is dropped with its newline, and ``^@@ .* @@`` becomes ``@@`` with the
    trailing newline kept -- and
    ``test_the_hash_equals_the_prose_pipeline_of_coordinator_md`` runs the real
    ``grep -v '^index ' | sed 's/^@@ .* @@/@@/' | sha256sum`` over the same bytes, so prose and
    code cannot drift apart quietly.

    A base roll changes only ``index`` lines and ``@@ -l,n +m,k @@`` headers, so its hash is
    unchanged (``carry: yes``); an author commit changes context or added lines, so it is not
    (``carry: no``).
    """
    kept = [ln for ln in diff.encode().splitlines(keepends=True) if not ln.startswith(b"index ")]
    return hashlib.sha256(HUNK_HEADER.sub(b"@@", b"".join(kept))).hexdigest()


def ur106_own_lines(diff: str) -> Counter[tuple[str, str, str]]:
    """A diff's added and removed lines as a multiset keyed ``(file, sign, content)``.

    UR-106's subset rule (ruling 278) defines _A_ and _N_ as "the added and removed lines
    (each with its file and sign)" -- context lines are not in the multisets, and neither
    are the ``index``/``---``/``+++`` metadata rows (a ``+index ...`` line IS an added
    line: the sign character decides, as the hash's adversarial pins already have it).
    The file is the ``diff --git`` line's b-side (the post-image path, what ``+++ b/``
    names too), so a new file's rows key on the real path rather than ``/dev/null``.
    """
    lines: Counter[tuple[str, str, str]] = Counter()
    file = ""
    for ln in diff.splitlines():
        if ln.startswith("diff --git "):
            m = re.match(r"diff --git a/(.*) b/(.*)$", ln)
            file = m.group(2) if m else ""
        elif ln.startswith(("---", "+++")):
            continue
        elif ln.startswith("+"):
            lines[(file, "+", ln[1:])] += 1
        elif ln.startswith("-"):
            lines[(file, "-", ln[1:])] += 1
    return lines


def ur106_subset_carry(
    approved_diff: str,
    head_diff: str,
    chain: list[list[str]],
    main_change: Callable[[], str | None],
    on_main: Callable[[str], bool | None],
) -> tuple[bool | None, int, str]:
    """UR-106's subset carry (ruling 278), decided: ``(yes|no|unknown, dropped lines, why)``.

    The rule: the new head carries when (1) every commit after the approved head is an
    ``update-branch`` merge of ``main``, (2) _N_, the new diff's added and removed lines,
    is contained in _A_, the approved diff's, as a multiset, and (3) every line in _A_ but
    not in _N_ appears, with the same file and sign, in ``main``'s own change between the
    two merge-bases. ``chain`` is the first-parent commits after the approved head, newest
    first, each as a parent list; ``main_change`` is read lazily -- only when lines are
    actually dropped -- and ``None`` means the read failed; ``on_main`` answers whether a
    merge's second parent sits on ``main``. Every ambiguity returns ``unknown``: a failed
    read is never a fact -- not yes, and not no (UR-106, UR-154).
    """
    if not chain:
        return None, 0, "no commits after the approved head -- the heads are unrelated"
    for parents in chain:
        if len(parents) < 2:
            return False, 0, "an author commit sits between the heads"
        on = on_main(parents[1])
        if on is None:
            return None, 0, "a merge parent's place on main is unread"
        if not on:
            return False, 0, "a merge between the heads is not of main"
    approved_lines, head_lines = ur106_own_lines(approved_diff), ur106_own_lines(head_diff)
    if head_lines - approved_lines:
        return False, 0, "the new diff holds a line the approved one does not"
    dropped = approved_lines - head_lines
    if not dropped:
        return True, 0, ""  # hunk noise only: the multisets already agree
    main_diff = main_change()
    if main_diff is None:
        return None, 0, "main's own change between the merge-bases is unread"
    if not dropped <= ur106_own_lines(main_diff):
        return False, 0, "main's own change does not hold a dropped line"
    return True, sum(dropped.values()), ""


def approval_sha(body: str) -> str | None:
    """The sha a ``Review: approve`` comment names.

    Looked for, in order: a backticked hex sha on the first line; any sha on a ``Head:`` or
    ``Head reviewed:`` line (the first one on it); a backticked sha in the first five lines.
    """
    lines = body.splitlines()
    if not lines:
        return None
    match = HEX_TICKED.search(lines[0])
    if match:
        return match.group(1)
    for line in lines:
        if HEAD_LINE.match(line):
            match = HEX_BARE.search(line)  # the first sha on the line, ticked or not
            if match:
                return match.group(1)
    for line in lines[:5]:
        match = HEX_TICKED.search(line)
        if match:
            return match.group(1)
    return None


# --- the snapshot --------------------------------------------------------------------------


class Snapshot:
    """Reads the repository once and holds the report as plain data."""

    def __init__(self, repo: str, runner: Runner, clock: Clock, since: datetime | None) -> None:
        self.repo = repo
        self.run = runner
        self.clock = clock
        self.since = since
        self.data: dict[str, Any] = {"repo": repo}

    def gh_paginated(self, path: str, *extra: str) -> list[Any]:
        return parse_json_stream(self.run(["gh", "api", path, "--paginate", *extra]))

    def git(self, *args: str) -> str:
        return self.run(["git", *args]).strip()

    def build(self) -> dict[str, Any]:
        heartbeat_comments = self._heartbeat_comments()
        self._cursor(heartbeat_comments)
        self._comments()
        self._binding_now()
        self._main()
        self._prs()
        self._heartbeats(heartbeat_comments)
        self._merged_audit()
        return self.data

    # 1. cursor -------------------------------------------------------------------------------

    def _heartbeat_comments(self) -> list[dict[str, Any]] | Exception:
        try:
            return self.gh_paginated(
                f"repos/{self.repo}/issues/{HEARTBEATS_ISSUE}/comments?per_page=100"
            )
        except Exception as exc:  # any failure is reported in its section, never fatal
            return exc

    def _cursor(self, heartbeat_comments: list[dict[str, Any]] | Exception) -> None:
        section: dict[str, Any] = {"heartbeat_id": None, "read_through": None, "errors": []}
        self.data["cursor"] = section
        start = self.clock()
        if isinstance(heartbeat_comments, Exception):
            section["errors"].append(error_text(heartbeat_comments))
        else:
            mine = [
                c
                for c in heartbeat_comments
                if (c.get("body") or "").startswith(COORDINATOR_MARKER)
            ]
            if not mine:
                section["errors"].append(f"no {COORDINATOR_MARKER} comment on #{HEARTBEATS_ISSUE}")
            else:
                section["heartbeat_id"] = mine[0]["id"]
                if len(mine) > 1:
                    section["duplicates"] = [c["id"] for c in mine[1:]]
                match = READ_THROUGH.search(mine[0].get("body") or "")
                if match:
                    try:
                        section["read_through"] = iso(parse_time(match.group(1)))
                    except ValueError:
                        section["errors"].append(f"unparsable read-through {match.group(1)!r}")
        if self.since is not None:
            cursor, source = self.since, "--since"
        elif section["read_through"]:
            cursor, source = parse_time(section["read_through"]), "heartbeat read-through"
        else:
            cursor, source = start - DEFAULT_LOOKBACK, "default: now - 2h (no read-through line)"
        section["cursor"] = iso(cursor)
        section["source"] = source

    # 2. comments -----------------------------------------------------------------------------

    def _comments(self) -> None:
        section: dict[str, Any] = {"items": [], "marker_count": 0, "bot": {}, "errors": []}
        self.data["comments"] = section
        now = self.clock()
        self.data["cursor"]["now"] = iso(now)
        self.now = now
        try:
            comments = self.gh_paginated(
                f"repos/{self.repo}/issues/comments?since={self.data['cursor']['cursor']}"
                "&per_page=100"
            )
        except Exception as exc:  # reported, not fatal
            section["errors"].append(error_text(exc))
            return
        for c in comments:
            line = first_line(c.get("body"))
            if is_marker(line):
                section["marker_count"] += 1
                continue
            author = (c.get("user") or {}).get("login") or ""
            if author.endswith("[bot]"):
                number = str(issue_number(c))
                section["bot"][number] = section["bot"].get(number, 0) + 1
                continue
            section["items"].append(self._comment_item(c, line))

    def _comment_item(self, c: dict[str, Any], line: str) -> dict[str, Any]:
        flag = None
        bare = undecorated(line)
        if bare.startswith("BINDING NOW"):
            live = self.now - parse_time(c["created_at"]) < BINDING_LIFE
            flag = "BINDING NOW live" if live else "BINDING NOW lapsed"
        elif bare.startswith("URGENT PATH"):
            flag = "URGENT PATH"
        return {
            "number": issue_number(c),
            "is_pr": "/pull/" in (c.get("html_url") or ""),
            "author": (c.get("user") or {}).get("login"),
            "created_at": c.get("created_at"),
            "updated_at": c.get("updated_at"),
            "id": c.get("id"),
            "first_line": truncate(line),
            "flag": flag,
            # Stamped here so §2's items and the activity extra-read are judged by the SAME
            # signature rule (§6's signs_agent reads these two, never a re-parse).
            "head_name": head_name(line),
            "review_lane": review_lane(c.get("body")),
        }

    def _binding_now(self) -> None:
        section: dict[str, Any] = {"items": [], "errors": []}
        self.data["binding_now"] = section
        # Owner records share this one read (the test pins the call set on #6854): the voice on
        # the owner's own issue that is neither a heartbeat nor the coordinator's status comment.
        records: dict[str, Any] = {"items": [], "errors": section["errors"]}
        self.data["owner_records"] = records
        window_start = self.now - BINDING_LIFE
        try:
            comments = self.gh_paginated(
                f"repos/{self.repo}/issues/{OWNER_ISSUE}/comments?since={iso(window_start)}"
                "&per_page=100"
            )
        except Exception as exc:  # reported, not fatal
            section["errors"].append(error_text(exc))
            return
        for c in comments:
            line = first_line(c.get("body"))
            created = parse_time(c["created_at"])
            if undecorated(line).startswith("BINDING NOW") and created > window_start:
                section["items"].append(
                    {
                        "id": c.get("id"),
                        "created_at": c["created_at"],
                        "lapses_at": iso(created + BINDING_LIFE),
                        "first_line": truncate(line),
                    }
                )
            if created > window_start and not is_marker(undecorated(line)):
                # UR-166's count window reads #6854's own voice -- UR-40 defines an *owner
                # record* as a comment on that issue, with BINDING NOW a property of some of
                # them -- minus the machine comments it also carries (the heartbeat row and the
                # coordinator's status comment, both marker-prefixed).
                records["items"].append(
                    {"id": c.get("id"), "created_at": c["created_at"], "text": c.get("body") or ""}
                )
        if records["items"]:
            # UR-166 part 9's window opens at the newest owner record; §8's window opens at the
            # cursor. They are different numbers on purpose -- see status_draft's test.
            newest = max(records["items"], key=lambda r: parse_time(r["created_at"]))
            records["newest"] = newest["created_at"]
            records["newest_id"] = newest["id"]

    # 5. main (read before the PRs: §4's behind read needs main's tip) -----------------------

    def _runs(self, workflow: str, limit: int, *extra: str) -> list[dict[str, Any]]:
        out = self.run(
            [
                "gh",
                "run",
                "list",
                "--repo",
                self.repo,
                "--branch",
                "main",
                "--workflow",
                workflow,
                "--limit",
                str(limit),
                *extra,
                "--json",
                "databaseId,status,conclusion,headSha,createdAt,event,url",
            ]
        )
        return json.loads(out or "[]")

    def _main(self) -> None:
        section: dict[str, Any] = {"errors": []}
        self.data["main"] = section
        try:
            self.git("fetch", "-q", "origin")
        except Exception as exc:  # reported, not fatal
            section["errors"].append(f"git fetch origin: {error_text(exc)}")
        try:
            section["tip"] = self.git("rev-parse", "origin/main")
        except Exception as exc:  # reported, not fatal
            section["errors"].append(f"tip: {error_text(exc)}")
        try:
            runs = self._runs("ci.yml", 10)
            tip = section.get("tip") or ""
            section["ci_latest"] = _run_summary(runs[0]) if runs else None
            at_tip = [r for r in runs if tip and r.get("headSha") == tip]
            section["ci_at_tip"] = _run_summary(at_tip[0]) if at_tip else None
            done = [
                r
                for r in runs
                if r.get("status") == "completed" and r.get("conclusion") != "cancelled"
            ]
            section["ci_last_completed"] = _run_summary(done[0]) if done else None
        except Exception as exc:  # reported, not fatal
            section["errors"].append(f"CI: {error_text(exc)}")
        for key, workflow, extra in (
            ("deploy", "deploy.yml", ()),
            ("nightly_full_gate", "nightly-full-gate.yml", ("--event", "schedule")),
            ("flaky_detection", "flaky-test-detection.yml", ()),
        ):
            try:
                runs = self._runs(workflow, 1, *extra)
                section[key] = _run_summary(runs[0]) if runs else None
            except Exception as exc:  # reported, not fatal
                section["errors"].append(f"{workflow}: {error_text(exc)}")

    def main_red(self) -> bool | None:
        last = self.data["main"].get("ci_last_completed")
        if last is None:
            return None
        return last["conclusion"] in RED_CONCLUSIONS

    # 3-4. PRs and merge state ---------------------------------------------------------------

    def _prs(self) -> None:
        section: dict[str, Any] = {"items": [], "errors": []}
        self.data["prs"] = section
        # §7 keys off this even when the PR read fails outright: a section that cannot be
        # computed prints as empty, it never takes the report down with it.
        self.data["auto_merge_watch"] = {"disable": [], "ok": [], "unknown": []}
        cmd = [
            "gh", "pr", "list", "--repo", self.repo, "--state", "open", "--limit", "200",
            "--json",
            "number,title,isDraft,labels,headRefOid,mergeStateStatus,autoMergeRequest,statusCheckRollup",
        ]  # fmt: skip
        prs = None
        for attempt in range(2):  # the rollup query is heavy; GitHub sometimes answers 504 once
            try:
                prs = json.loads(self.run(cmd) or "[]")
                break
            except Exception as exc:  # reported, not fatal
                if attempt == 1:
                    section["errors"].append(error_text(exc))
        if prs is None:
            return
        prs.sort(key=lambda p: p["number"])
        if prs:
            refspecs = [
                f"+refs/pull/{p['number']}/head:refs/remotes/origin/pr/{p['number']}" for p in prs
            ]
            try:
                self.git("fetch", "-q", "origin", *refspecs)
            except Exception as exc:  # reported, not fatal
                section["errors"].append(f"git fetch PR heads: {error_text(exc)}")
        for pr in prs:
            item = self._pr_item(pr)
            section["items"].append(item)
        self.data["auto_merge_watch"] = self._watch(section["items"])

    def _watch(self, items: list[dict[str, Any]]) -> dict[str, list[int]]:
        """UR-108's three-way sort of armed PRs. An unread carry is ``unknown``, never
        ``disable``: the coordinator disables on evidence, and a failed read is not evidence
        that the head is unapproved. The identity case (``carry: True`` with no reads) is ok."""
        watch: dict[str, list[int]] = {"disable": [], "ok": [], "unknown": []}
        for item in items:
            if not item.get("armed"):
                continue
            carry = (item.get("own_diff") or {}).get("carry")
            if carry is False:
                watch["disable"].append(item["number"])
            elif carry is None:
                watch["unknown"].append(item["number"])
            else:
                watch["ok"].append(item["number"])
        return watch

    def _rollup(self, pr: dict[str, Any], errors: list[str]) -> list[dict[str, Any]]:
        """The PR's check runs, re-read per-PR only when the batch is known-truncated.

        The list query caps each PR's rollup at ``LIST_ROLLUP_CAP`` entries, so a batch of
        exactly that length says nothing about whether a gate exists — which is how a green
        gate got printed as ``absent``. A short batch with no gate is a real "absent" and stays
        free; only the suspect PR pays one extra read.
        """
        rollup = pr.get("statusCheckRollup") or []
        if len(rollup) < LIST_ROLLUP_CAP:
            return rollup
        cmd = [
            "gh", "pr", "view", str(pr["number"]), "--repo", self.repo,
            "--json", "statusCheckRollup",
        ]  # fmt: skip
        try:
            full = json.loads(self.run(cmd) or "{}").get("statusCheckRollup") or []
        except Exception as exc:  # reported, not fatal: keep the truncated read and say so
            errors.append(f"rollup re-read (batch capped at {LIST_ROLLUP_CAP}): {error_text(exc)}")
            return rollup
        return full or rollup

    def _pr_item(self, pr: dict[str, Any]) -> dict[str, Any]:
        head = pr.get("headRefOid") or ""
        errors: list[str] = []
        rollup = self._rollup(pr, errors)
        item: dict[str, Any] = {
            "number": pr["number"],
            "title": truncate(pr.get("title") or "", 70),
            "draft": bool(pr.get("isDraft")),
            "labels": [lbl["name"] for lbl in pr.get("labels") or []],
            "head": head,
            "merge_state": pr.get("mergeStateStatus"),
            "gate": gate_state(rollup),
            "gate_run": gate_run_id(rollup),
            "armed": bool(pr.get("autoMergeRequest")),
            "errors": errors,
        }
        try:
            item["merge_base"] = self.git("merge-base", "origin/main", head)
        except Exception as exc:  # reported, not fatal
            item["merge_base"] = None
            item["errors"].append(f"merge-base: {error_text(exc)}")
        if item["draft"]:
            return item
        self._review(item)
        if item["merge_base"]:  # every non-draft PR: behind needs no gate; the sign's
            self._merge_state(item)  # gate-unfinished factor counts absent as unfinished
        return item

    def _review(self, item: dict[str, Any]) -> None:
        try:
            reviews = self.gh_paginated(
                f"repos/{self.repo}/issues/{item['number']}/comments?per_page=100",
                "--jq",
                REVIEWS_JQ,
            )
        except Exception as exc:  # reported, not fatal
            item["errors"].append(f"reviews: {error_text(exc)}")
            return
        self.judge(item, reviews, judged_first=True)

    def judge(
        self, item: dict[str, Any], reviews: list[dict[str, Any]], judged_first: bool
    ) -> None:
        """The approval verdict and the UR-106 carry, for an open PR or a merged one.

        One code path for both, so §3 and §8 cannot disagree about what an approval is worth: the
        rev under judgment is an open PR's head or a merged PR's landed head, and everything
        below reads the same way for each.
        """
        reviews.sort(key=lambda r: r.get("created_at") or "")
        if reviews:
            item["latest_review"] = truncate(first_line(reviews[-1]["body"]), 60)
        approvals = [r for r in reviews if is_approval(first_line(r["body"]))]
        if not approvals:
            item["approval"] = None
            return
        newest = approvals[-1]
        sha = approval_sha(newest["body"])
        rev = item["head"]
        matches = bool(sha) and rev.startswith(sha)
        item["approval"] = {
            "id": newest["id"],
            "by": newest.get("user"),
            "sha": sha,
            "matches_head": matches,
        }
        if matches:
            # The approved rev *is* the rev under judgment: the carry is settled by identity and
            # no diff is read. Hashing a rev against itself would report a carry for free -- the
            # vacuity the merged path dodges by reaching for the merge commit's parents -- and
            # the merged test that counts reads (one per rev of a *differing* approval) depends
            # on an identity approval costing none.
            item["own_diff"] = {"head": None, "approved": None, "carry": True, "reads": 0}
        elif not sha:
            item["own_diff"] = {
                "head": None,
                "approved": None,
                "carry": None,
                "reads": 0,
                "error": "the approval names no sha",
            }
            item["verdict_reason"] = "the approval names no sha"
        else:
            self._own_diff(item, sha, judged_first)

    def _own_diff(self, item: dict[str, Any], approved: str, judged_first: bool) -> None:
        """UR-106's own-diff hashes, for an approval on a rev *other* than the one judged.

        Each rev is hashed against *its own* merge-base, ``merge-base <root> <rev>`` per rev: a
        base roll moves ``merge-base origin/main <head>``, and the rolled base is not an ancestor
        of the old approved sha, so hashing both revs against today's merge-base reports
        ``carry: no`` for a roll that carries. ``approved`` is the string the review names -- a
        7-hex prefix in the wild -- handed to git verbatim, because git resolves an unambiguous
        abbreviation itself and UR-106's prose pipeline never sees a full sha either.

        Read order is §3's (judged rev first) and §8's (approved first) in one primitive, chosen
        by ``judged_first``, so the two sections order their git calls as their tests pin them.
        """
        own: dict[str, Any] = {"head": None, "approved": None, "carry": None, "reads": 0}
        item["own_diff"] = own
        files = self._pr_files(item["number"], item["errors"])
        if files is None:
            own["error"] = "the PR's files are unread"
            return
        root = item.get("diff_root") or "origin/main"
        if judged_first:
            own["head"] = self._hash_own(item, root, item["head"], files, own)
            own["approved"] = self._hash_own(item, root, approved, files, own)
        else:
            own["approved"] = self._hash_own(item, root, approved, files, own)
            own["head"] = self._hash_own(item, root, item["head"], files, own)
        if own["head"] is None or own["approved"] is None:
            own["error"] = own.get("error") or "a rev needed for the carry is unhashed"
            item["verdict_reason"] = own["error"]
            return
        if own["head"] == own["approved"]:
            own["carry"] = True
            return
        own.update(self._subset_carry(item, approved, files, own))

    def _subset_carry(
        self,
        item: dict[str, Any],
        approved: str,
        files: list[str],
        own: dict[str, Any],
    ) -> dict[str, Any]:
        """The two extra reads the subset path (ruling 278) adds, decided once.

        The hash path already proved the two own diffs differ, so the question is the
        subset rule: only update-branch merges between the heads (condition 1), N ⊆ A as
        a multiset (condition 2), and main's own change between the two merge-bases
        holding every dropped line (condition 3). The approved head's own diff is already
        hashed at its own base; the head's diff is re-derived here from the hash path's
        base -- the same ``base..head`` range the hash read, so no extra git read pays
        for the text this path needs but hashing threw away.

        Every ambiguous read is ``unknown``: the coordinator hand-judges, the watch never
        disables, and a failed read is never a yes (UR-106, UR-154).
        """
        head = item["head"]
        approved_base, head_base = own.get("approved_base") or "", own.get("head_base") or ""
        reads: dict[str, Any] = {"carry": None, "subset_lines": 0}
        try:
            out = self.git(
                "log", "--first-parent", "--format=%P", f"{approved}..{head}"
            )
            chain = [line.split() for line in out.splitlines() if line.strip()]
        except Exception as exc:
            reads["error"] = f"subset chain: {error_text(exc)}"
            item["errors"].append(f"subset chain: {error_text(exc)}")
            return reads

        def main_change() -> str | None:
            # main's OWN change between the two merge-bases: from the approved head's
            # merge-base to the head's, over the PR's files -- the third diff condition 3
            # reads dropped lines against. Both bases came from the hash path's per-rev
            # merge-base reads, so this costs no extra base lookup.
            try:
                return self.run(
                    [
                        "git", "diff", f"{approved_base}..{head_base}", "--",
                        *(f":(literal){f}" for f in files),
                    ]
                )
            except Exception as exc:
                item["errors"].append(f"main between bases: {error_text(exc)}")
                return None

        def on_main(parent: str) -> bool | None:
            return self._on_main(parent, item)

        verdict, lines, why = ur106_subset_carry(own["approved_diff"], own["head_diff"], chain, main_change, on_main)
        if verdict is True:
            reads["carry"], reads["subset_lines"] = True, lines
        elif verdict is False:
            reads["carry"], reads["error"] = False, why
        else:
            reads["error"] = why or "a subset read failed"
        return reads

    def _on_main(self, parent: str, item: dict[str, Any]) -> bool | None:
        """Whether ``parent`` sits on ``main``: it holds no commit main's tip lacks, i.e.
        ``rev-list --count parent --not origin/main`` is 0 (an ancestor of, or is, the
        tip). A read failure returns ``None`` -- unknown, never a fact (UR-154)."""
        try:
            count = int(self.git("rev-list", "--count", parent, "--not", "origin/main"))
            return count == 0
        except Exception as exc:
            item["errors"].append(f"on-main {parent[:9]}: {error_text(exc)}")
            return None

    def _hash_own(
        self,
        item: dict[str, Any],
        root: str,
        rev: str,
        files: list[str],
        own: dict[str, Any],
    ) -> str | None:
        """``sha256`` of the rev's own diff at its own merge-base, or None with an error named
        ``own-diff`` -- a failed read must never read as a carry (UR-106, UR-154). The paths
        ride as ``:(literal)`` pathspecs: a PR-controlled filename like ``:(exclude)**`` would
        otherwise rewrite the diff's pathspec and read as an empty diff (a false carry)."""
        try:
            base = self.git("merge-base", root, rev)
            diff = self.run(
                ["git", "diff", f"{base}..{rev}", "--", *(f":(literal){f}" for f in files)]
            )
        except Exception as exc:  # reported, not fatal; carry stays None
            item["errors"].append(f"own-diff {rev[:9]}: {error_text(exc)}")
            own["reads"] += 1
            return None
        own["reads"] += 1
        own["head_base" if rev == item["head"] else "approved_base"] = base
        own[f"{'head' if rev == item['head'] else 'approved'}_diff"] = diff
        return ur106_diff_hash(diff)

    def _pr_files(self, number: int, errors: list[str]) -> list[str] | None:
        """The PR's own paths, which bound the UR-106 diff to the PR: the full-tree diff would
        fold in main's changes and the hash would move with every roll of main."""
        cmd = [
            "gh", "pr", "view", str(number), "--repo", self.repo, "--json", "files",
        ]  # fmt: skip
        try:
            files = json.loads(self.run(cmd) or "{}").get("files") or []
        except Exception as exc:  # reported into the caller's own error list
            errors.append(f"own-diff files of #{number}: {error_text(exc)}")
            return None
        return [f["path"] for f in files if f.get("path")]

    # 8. merged audit -------------------------------------------------------------------------

    def _merged_audit(self) -> None:
        """Every PR merged since the cursor, judged as UR-164 step 12 asks: did the head that
        landed match what was approved, or is it a UR-106 carry of it, and does an owner record
        bar it? The window is the CURSOR's; UR-166 part 9's count is a different window -- since
        the newest owner record -- so both are computed from one scan here."""
        section: dict[str, Any] = {
            "items": [],
            "errors": [],
            "since": self.data["cursor"]["cursor"],
            "scanned": 0,
            "possibly_more": False,
        }
        self.data["merged_audit"] = section
        window = self._merged_window(section)
        since_owner = self.data["owner_records"].get("newest")
        self.data["merged_window"] = {
            "since": since_owner,
            "count": (
                sum(1 for r in window if parse_time(r["merged_at"]) > parse_time(since_owner))
                if since_owner
                else None
            ),
            "errors": [],
        }
        cursor = parse_time(section["since"])
        holds = self._owner_holds()
        for row in window:
            if parse_time(row["merged_at"]) <= cursor:
                continue  # outside the audit window: not one per-PR read
            section["items"].append(self._merge_item(row, holds))

    def _merged_window(self, section: dict[str, Any]) -> list[dict[str, Any]]:
        """The merged PRs, newest-updated first. REST has no ``since`` for pulls, so this is a
        client-side filter; ``sort=updated`` makes it sound to stop at the first row whose
        ``updated_at`` predates the cursor, because a merge inside the window updated the PR."""
        try:
            rows = self.gh_paginated(
                f"repos/{self.repo}/pulls?state=closed&sort=updated&direction=desc&per_page=100",
                "--jq",
                "[.[] | select(.merged_at != null) | "
                "{number, title, merged_at, updated_at, merge_commit_sha, body,"
                " user: .user.login}]",
            )
        except Exception as exc:  # reported, not fatal
            section["errors"].append(f"merged list: {error_text(exc)}")
            return []
        section["scanned"] = len(rows)
        cursor = parse_time(section["since"])
        live = [r for r in rows if parse_time(r["merged_at"]) > cursor]
        if len(rows) >= SCAN_PAGE and rows and parse_time(rows[-1]["updated_at"]) > cursor:
            section["possibly_more"] = True
        live.sort(key=lambda r: parse_time(r["merged_at"]))
        self._merged_rows = live
        return [r for r in rows if r.get("merged_at")]

    def _owner_holds(self) -> list[tuple[int, str]]:
        """``(pr number, first line)`` for each owner hold on #6854 -- the owner's voice only."""
        holds: list[tuple[int, str]] = []
        for rec in self.data["owner_records"]["items"]:
            text = rec["text"]
            line = first_line(text)
            if not OWNER_VOICE.match(undecorated(line)) or not OWNER_HOLD.search(text):
                continue
            for number in OWNER_PR_REF.findall(text):
                holds.append((int(number), truncate(line, 90)))
        return holds

    def _merge_item(self, row: dict[str, Any], holds: list[tuple[int, str]]) -> dict[str, Any]:
        number = row["number"]
        merge = row.get("merge_commit_sha") or ""
        item: dict[str, Any] = {
            "number": number,
            "title": truncate(row.get("title") or "", 70),
            "merged_at": row.get("merged_at"),
            "merge": merge,
            "errors": [],
        }
        barred = [h for h in holds if h[0] == number]
        body = row.get("body") or ""
        if not barred and BODY_HOLD.search(body):
            # A hold recorded in the PR's own Notes (the lane quoting an owner instruction into
            # the body, the ``Notes:`` slot ruling 156 uses) bars its own PR. It is checked in
            # addition to the #6854 holds, not instead: the owner can hold a PR by ruling or in
            # the body, and a merge audit that reads only one of the two misses the other.
            held_line = next(ln for ln in body.splitlines() if BODY_HOLD.match(ln))
            barred = [(number, truncate(held_line.strip(), 90))]
        landed = None
        reviews = self._merge_reviews(number)
        approvals = (
            []
            if isinstance(reviews, Exception)
            else [r for r in reviews if is_approval(first_line(r["body"]))]
        )
        if merge and not (isinstance(reviews, Exception) or not approvals):
            # The parents only matter once something was approved: "no approving review" is the
            # verdict the audit exists to print, and it needs no git read to say it.
            try:
                landed = self.git("rev-parse", f"{merge}^2")
                item["landed"] = landed
                item["main_at_merge"] = self.git("rev-parse", f"{merge}^1")
            except Exception as exc:  # reported, not fatal
                item["errors"].append(f"merge parents of {merge[:9]}: {error_text(exc)}")
        if isinstance(reviews, Exception):
            item["errors"].append(f"reviews: {error_text(reviews)}")
            item["verdict"] = f"unknown: reviews unread ({error_text(reviews)})"
        elif not approvals:
            item["approval"] = None
            item["verdict"] = "no approving review"
        elif landed is None:
            item["verdict"] = "unknown: the merge commit's landed head is unread"
        else:
            # The base root is main *at the merge*, not the live origin/main: a merged head is an
            # ancestor of the merge commit, so merge-base origin/main <head> IS the head, the own
            # diff is empty, and every carry check passes for free.
            item["head"] = landed
            item["diff_root"] = item.get("main_at_merge") or "origin/main"
            self.judge(item, reviews, judged_first=False)
            carry = (item.get("own_diff") or {}).get("carry")
            named = (item.get("approval") or {}).get("sha") or ""
            if carry is True:
                # Two ways a merge holds: the approval names the landed head (identity -- no diff
                # read, a 7-char prefix never startswith-matches a 40-char landed sha), or the
                # landed head is a UR-106 carry of what was approved, which cost two reads.
                item["verdict"] = "ok" if not item["own_diff"]["reads"] else "ok (UR-106 carry)"
            elif carry is False:
                item["verdict"] = (
                    f"NOT APPROVED at the landed head `{landed[:9]}` (approved `{named[:9]}`)"
                )
            else:
                item["verdict"] = f"unknown: {item.get('verdict_reason', 'carry unread')}"
        item["carry"] = (item.get("own_diff") or {}).get("carry")
        if barred:
            item["barred_by"] = [h[1] for h in barred]
            item["verdict"] = f"BARRED by owner: {barred[0][1]}"
        item["merge_comment"] = self._merge_comment(item)
        return item

    def _merge_reviews(self, number: int) -> list[dict[str, Any]] | Exception:
        try:
            return self.gh_paginated(
                f"repos/{self.repo}/issues/{number}/comments?per_page=100", "--jq", REVIEWS_JQ
            )
        except Exception as exc:  # the caller reports it as its own verdict gap
            return exc

    def _merge_comment(self, item: dict[str, Any]) -> str:
        """The UR-29 merge comment pre-filled, with what this snapshot never read marked
        ``unread`` rather than omitted (UR-154: a clean-looking comment that hides a gap is
        worse than an untidy one)."""
        number = item["number"]
        lines = [
            f"Merged #{number} {item['title']} at `{(item.get('merge') or '?')[:9]}`"
            f" (landed head `{(item.get('landed') or '?')[:9]}`).",
            f"verdict: {item['verdict']}",
            "checks: unread (the snapshot ran after the merge; read the run before posting)",
            "no owner ruling names this PR"
            if not item.get("barred_by")
            else "owner hold: " + "; ".join(item["barred_by"]),
        ]
        return "\n".join(lines)

    def _merge_state(self, item: dict[str, Any]) -> None:
        """§4's two reads per non-draft PR (ruling 270): behind main, and the in-flight sign
        that `roles/coordinator.md` "Merging a PR" step 1 names — the state an update-branch
        leaves while the PR's CI runs at the new head."""
        # Both reads measure §3's `base=` — the merge-base — because that is the line the
        # coordinator reads: ruling 270 item 2 says "its `base=` is not `main`'s tip" / "its
        # `base=` is at the tip", and with `strict: true` only §3's `base=` says whether a PR
        # is behind `main` ("Merging a PR" step 2, via the coordinator's header). The gate
        # run's merged base was the old legs' basis; step 1/2 decide from the printed base=.
        base = item["merge_base"]
        tip = self.data["main"].get("tip")
        if not tip:
            item["behind"] = {"error": "main tip unread"}
        elif not base:
            item["behind"] = {"error": "no base to compare"}
        else:
            try:
                behind = int(
                    self.git("rev-list", "--count", "--first-parent", f"{base}..origin/main")
                )
                item["behind"] = {"merges": behind, "at_tip": behind == 0}
            except Exception as exc:  # reported, not fatal
                item["behind"] = {"error": error_text(exc)}
        # The in-flight sign: base at the tip, the gate not finished, and the approval carries.
        # The package's gate list names step 1's three ("absent" until the gate job is queued, then
        # QUEUED or IN_PROGRESS); PENDING is the StatusContext spelling of in-flight, which a
        # combined-context rollup can carry for the gate.
        gate_status = (item.get("gate") or "").upper()  # "absent" is the one lowercase verdict
        gate_unfinished = gate_status in ("ABSENT", "QUEUED", "IN_PROGRESS", "PENDING")
        item["in_flight"] = {
            "base_at_tip": item.get("behind", {}).get("at_tip"),
            "gate_unfinished": gate_unfinished,
            "carry": item.get("own_diff", {}).get("carry"),
            "yes": (
                item.get("behind", {}).get("at_tip") is True
                and gate_unfinished
                and item.get("own_diff", {}).get("carry") is True
            ),
        }

    # 6. heartbeats ---------------------------------------------------------------------------

    def _heartbeats(self, heartbeat_comments: list[dict[str, Any]] | Exception) -> None:
        section: dict[str, Any] = {"items": [], "errors": []}
        self.data["heartbeats"] = section
        if isinstance(heartbeat_comments, Exception):
            section["errors"].append(error_text(heartbeat_comments))
            return
        for c in heartbeat_comments:
            agent = heartbeat_agent(c.get("body"))
            if agent is None:
                continue
            body = (c.get("body") or "").lstrip()
            age = (self.now - parse_time(c["updated_at"])).total_seconds() / 60
            lines = body.splitlines()
            head_lines = "\n".join(lines[:3]).lower()
            section["items"].append(
                {
                    "agent": agent,
                    "id": c.get("id"),
                    "updated_at": c["updated_at"],
                    # Ruling 181: what the agent said it was doing, kept for the lane digest, which
                    # prints its own beat's prose beside its age. The paused check above reads the
                    # same lines; neither caller re-parses the body. The beat's own marker line is
                    # skipped, so the head is prose and not the machine line that keys the row.
                    "head": truncate(next((ln for ln in lines[1:] if ln.strip()), ""), 70),
                    "age_min": round(age, 1),
                    "paused": is_paused(head_lines),
                    "stale": age > stale_threshold(agent),
                    # Ruling 181: the third line a blocked lane is allowed to carry.
                    "blocker": next(
                        (
                            ln.strip()
                            for ln in body.splitlines()
                            if undecorated(ln).startswith("BLOCKER:")
                        ),
                        None,
                    ),
                }
            )
        self._activity(section)

    def _activity(self, section: dict[str, Any]) -> None:
        """Ruling 178's signed activity, beside each non-paused agent's age.

        Read from what this tick already fetched: §2's comments and §3's PR heads
        (``refs/remotes/origin/pr/<n>``), so the commit leg costs local ``git log`` only. One
        extra comment call happens only when some non-paused beat predates §2's cursor -- and it
        must happen then, because §2's window would otherwise miss that agent's activity and the
        section would print a silence that reads "no activity since the beat" for comments the
        snapshot never fetched. That is the difference between an unread section and an empty one.
        """
        live = [h for h in section["items"] if not h["paused"]]
        for h in live:
            h["lane"], h["cell"] = agent_key(h["agent"])
        if not live:
            return
        cursor = self.data["cursor"]["cursor"]
        seen = {c["id"]: c for c in self.data["comments"]["items"]}
        window = min((h["updated_at"] for h in live if h["updated_at"] < cursor), default=None)
        if window:
            try:
                raw = self.gh_paginated(
                    f"repos/{self.repo}/issues/comments?since={window}&per_page=100"
                )
            except Exception as exc:  # the silence below is then labelled, not silent
                section["errors"].append(f"activity since {window}: {error_text(exc)}")
                raw = []
            for c in raw:
                line = first_line(c.get("body"))
                author = (c.get("user") or {}).get("login") or ""
                if c.get("id") in seen or is_marker(line) or author.endswith("[bot]"):
                    continue
                seen[c["id"]] = self._comment_item(c, line)
        comments = list(seen.values())
        owned: dict[tuple[str, str | None], list[int]] = {}
        unnamed: dict[str, list[int]] = {}
        for item in self.data["prs"].get("items", []):
            who = owner_of_pr(item["labels"])
            if who is None:
                continue
            lane, cell, definite = who
            if definite:
                owned.setdefault((lane, cell), []).append(item["number"])
            else:  # a two-cell lane's PR with no cell row: nobody's to claim, everybody's to see
                unnamed.setdefault(lane, []).append(item["number"])
        for h in live:
            signed = [
                (c, signs_agent(c, h["lane"], h["cell"]))
                for c in comments
                if c["updated_at"] >= h["updated_at"]
            ]
            signed = [(c, sign) for c, sign in signed if sign]
            signed.sort(key=lambda pair: pair[0]["updated_at"])
            # The newest, as ruling 178 reads it, with the reading that made it count.
            h["signed_comment"] = {**signed[-1][0], "sign": signed[-1][1]} if signed else None
            commits, unread = [], []
            for number in owned.get((h["lane"], h["cell"]), []):
                try:
                    out = self.git(
                        "log",
                        f"--since={h['updated_at']}",
                        "--format=%ct%x09%H%x09%s",
                        f"refs/remotes/origin/pr/{number}",
                    )
                    for row in out.splitlines():
                        epoch, sha, subject = row.split("\t", 2)
                        # ISO, not the raw epoch: an ISO stamp sorts chronologically as a string
                        # (a digit-count change would make an epoch sort wrong) and prints
                        # readable, in the same unit as every other time in the report.
                        commits.append(
                            (iso(datetime.fromtimestamp(int(epoch), UTC)), number, sha, subject)
                        )
                except Exception as exc:
                    unread.append(f"#{number}: {error_text(exc)}")
            commits.sort()
            h["commits"] = [
                {"stamp": s, "number": n, "sha": h_, "subject": truncate(subj, 70)}
                for s, n, h_, subj in commits[-3:]
            ]
            h["commit_count"] = len(commits)
            h["commit_errors"] = unread
            h["uncellated_prs"] = sorted(unnamed.get(h["lane"], []))


def _run_summary(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": run.get("databaseId"),
        "status": run.get("status"),
        "conclusion": run.get("conclusion") or None,
        "head": (run.get("headSha") or "")[:9],
        "created_at": run.get("createdAt"),
        "event": run.get("event"),
    }


def gate_check(rollup: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The newest ``CI Gate (Required Checks)`` entry in a PR's statusCheckRollup."""
    gates = [c for c in rollup if (c.get("name") or c.get("context")) == GATE_CHECK]
    if not gates:
        return None
    return max(gates, key=lambda c: c.get("startedAt") or "")


def gate_run_id(rollup: list[dict[str, Any]]) -> int | None:
    """The Actions run behind the gate check, from its ``detailsUrl``."""
    gate = gate_check(rollup) or {}
    match = RUN_ID.search(gate.get("detailsUrl") or gate.get("targetUrl") or "")
    return int(match.group(1)) if match else None


def gate_state(rollup: list[dict[str, Any]]) -> str:
    """``CI Gate (Required Checks)`` at the head: its conclusion, its status if running, or absent."""
    gate = gate_check(rollup)
    if gate is None:
        return "absent"
    conclusion = gate.get("conclusion") or gate.get("state") or ""
    if conclusion:
        return conclusion.upper()
    return (gate.get("status") or "unknown").upper()


# --- rendering ------------------------------------------------------------------------------


def _errors(name: str, section: dict[str, Any]) -> list[str]:
    return [f"  ERROR {name}: {e}" for e in section.get("errors", [])]


def _hash_txt(h: str | None) -> str:
    return h[:12] if h else "unread"


def _run_text(run: dict[str, Any] | None) -> str:
    if not run:
        return "none"
    state = run["conclusion"] or run["status"]
    return f"{state} at {run['head']} ({run['created_at']}, run {run['id']})"


def render_text(data: dict[str, Any]) -> str:
    out: list[str] = [f"coordinator snapshot · {data['repo']}"]

    cur = data["cursor"]
    out.append("== 1. cursor")
    out.append(f"  cursor {cur['cursor']} ({cur['source']})  heartbeat {cur['heartbeat_id']}")
    out.append(f"  now {cur.get('now')}  <- write this back as read-through, last")
    if cur.get("duplicates"):
        out.append(f"  duplicate coordinator heartbeats: {cur['duplicates']}")
    out += _errors("cursor", cur)

    com = data["comments"]
    out.append(f"== 2. comments since cursor: {len(com['items'])} listed")
    for c in com["items"]:
        kind = "PR" if c["is_pr"] else "#"
        flag = f" [{c['flag']}]" if c["flag"] else ""
        out.append(
            f"  {kind}{c['number']} {c['author']} c={c['created_at']} u={c['updated_at']} "
            f"id={c['id']}{flag}: {c['first_line']}"
        )
    out.append(f"  ({com['marker_count']} heartbeat/status-marker comments counted, not listed)")
    if com["bot"]:
        bots = " ".join(f"#{n}x{k}" for n, k in sorted(com["bot"].items()))
        out.append(f"  ({sum(com['bot'].values())} bot comments counted, not listed: {bots})")
    out += _errors("comments", com)
    bn = data["binding_now"]
    out.append(f"  live BINDING NOW on #{OWNER_ISSUE} (last 48 h): {len(bn['items']) or 'none'}")
    for b in bn["items"]:
        out.append(f"    {b['id']} {b['created_at']} lapses {b['lapses_at']}: {b['first_line']}")
    out += _errors("binding_now", bn)

    prs = data["prs"]
    out.append(f"== 3. open PRs: {len(prs['items'])}")
    for p in prs["items"]:
        draft = "draft" if p["draft"] else "ready"
        base = (p.get("merge_base") or "?")[:9]
        line = (
            f"  #{p['number']} {draft} head={p['head'][:9]} base={base} "
            f"{p['merge_state']} gate={p['gate']}"
        )
        if not p["draft"]:
            appr = p.get("approval")
            if appr:
                if not appr["sha"]:
                    line += f" approve=?(names no sha, {appr['id']})"
                else:
                    match = "=head" if appr["matches_head"] else "STALE"
                    line += f" approve={appr['sha'][:9]}({match}, {appr['id']})"
            elif "approval" in p:
                line += " approve=none"
            if p.get("armed"):
                line += " armed"
        out.append(line)
        labels = ",".join(p["labels"]) or "-"
        out.append(f"      {p['title']} [{labels}]")
        if p.get("latest_review") and not is_approval(p["latest_review"]):
            out.append(f"      latest review: {p['latest_review']}")
        own = p.get("own_diff")
        if own:
            head_h, appr_h = own.get("head"), own.get("approved")
            carry = own.get("carry")
            txt = {True: "yes", False: "no", None: "?"}[carry]
            subset = (
                f" (subset: {own['subset_lines']} lines main holds)"
                if carry is True and own.get("subset_lines")
                else ""
            )
            out.append(
                f"      own-diff head={_hash_txt(head_h)} approved={_hash_txt(appr_h)}"
                f" carry={txt}{subset}" + (f" ({own['error']})" if own.get("error") else "")
            )
        out += [f"      ERROR prs: {e}" for e in p["errors"]]
    out += _errors("prs", prs)

    out.append("== 4. merge state (ruling 270), non-draft PRs")
    any_state = False
    for p in prs["items"]:
        behind, inflight = p.get("behind"), p.get("in_flight")
        if behind is None and inflight is None:
            continue
        any_state = True
        base = (p.get("merge_base") or "?")[:9]
        out.append(f"  #{p['number']} base: merge-base {base}")
        if isinstance(behind, dict) and "error" in behind:
            b_txt = behind["error"]
        else:
            b_txt = f"{behind['merges']} merges behind" + (
                " (at tip)" if behind.get("at_tip") else ""
            )
        out.append(
            f"      behind main: {b_txt}"
            if "error" in behind
            else f"      behind main: {'yes' if not behind['at_tip'] else 'no'} ({b_txt})"
        )
        if inflight:
            out.append(
                f"      in-flight sign: {'yes' if inflight['yes'] else 'no'} "
                f"(base at tip {'yes' if inflight['base_at_tip'] else 'no'} · "
                f"gate {p['gate']} · carry "
                f"{ {True: 'yes', False: 'no', None: '?'}[inflight['carry']] })"
            )
    if not any_state:
        out.append("  none")

    main = data["main"]
    out.append("== 5. main")
    out.append(f"  tip {(main.get('tip') or '?')[:9]}")
    out.append(f"  CI latest: {_run_text(main.get('ci_latest'))}")
    out.append(f"  CI at tip: {_run_text(main.get('ci_at_tip'))}")
    out.append(f"  CI last completed (not cancelled): {_run_text(main.get('ci_last_completed'))}")
    out.append(f"  Deploy: {_run_text(main.get('deploy'))}")
    out.append(f"  Nightly Full Gate (schedule): {_run_text(main.get('nightly_full_gate'))}")
    out.append(f"  Flaky Test Detection: {_run_text(main.get('flaky_detection'))}")
    out += _errors("main", main)

    hb = data["heartbeats"]
    out.append(f"== 6. heartbeats on #{HEARTBEATS_ISSUE}: {len(hb['items'])}")
    for h in hb["items"]:
        flags = []
        if h["paused"]:
            flags.append("paused")
        if h["stale"]:
            flags.append(f"STALE >{stale_threshold(h['agent'])}m")
        # Ruling 245 ([r239] box 4), beside UR-162's flag -- a different rule about the same beat.
        # UR-38's stall is age past three of the agent's own intervals AND silence (no signed
        # comment, no commits since the beat); UR-160's paused agent is never stalled, and rows
        # `_activity` skipped (paused, or the section errored) carry no activity read at all.
        if not h["paused"] and h.get("signed_comment", h.get("commit_count")) is None:
            silent = h.get("signed_comment") is None and h.get("commit_count", 0) == 0
            if silent and h["age_min"] > stall_threshold(h["agent"]):
                flags.append(f"stalled >{stall_threshold(h['agent'])}m")
        flag = f" [{', '.join(flags)}]" if flags else ""
        out.append(f"  {h['agent']} {h['updated_at']} age {h['age_min']}m id={h['id']}{flag}")
        if h.get("blocker"):
            out.append(f"      {h['blocker']}")
        if h["paused"]:
            continue  # UR-160: a paused agent is not stalled, so its activity is not asked for
        if sc := h.get("signed_comment"):
            kind = {"self": "signed", "lane": "lane-named, cell not stated"}[sc["sign"]]
            where = "PR" if sc["is_pr"] else "#"
            out.append(
                f"      activity: {where}{sc['number']} u={sc['updated_at']} "
                f"id={sc['id']} ({kind}): {sc['first_line']}"
            )
        else:
            out.append("      activity: none signed since the beat")
        count = h.get("commit_count", 0)
        for c in h.get("commits", []):
            out.append(f"      commit #{c['number']} {c['sha'][:9]} {c['stamp']} {c['subject']}")
        out.append(
            f"      {count} commit(s) since the beat"
            + (f" ({count - 3} more)" if count > 3 else "")
        )
        for err in h.get("commit_errors", []):
            out.append(f"      ERROR commits: {err}")
        if h.get("uncellated_prs"):
            loose = ", ".join(f"#{v}" for v in h["uncellated_prs"])
            out.append(f"      uncellated {h['lane']} PR(s), either cell: {loose}")
    out += _errors("heartbeats", hb)

    watch = data["auto_merge_watch"]
    out.append("== 7. auto-merge (UR-108)")
    for key, label in (("disable", "auto-merge to disable"), ("ok", "ok"), ("unknown", "unknown")):
        nums = ", ".join(f"#{n}" for n in watch[key]) or "none"
        out.append(f"  {label}: {nums}")
    out.append(
        "  a UR-108 disable needs the owner's own ruling naming the PR; an unknown carry is "
        "not evidence to disable -- read the diff, then act"
    )

    au = data["merged_audit"]
    since = f"{au['since']} (read {au['scanned']} closed PRs)" + (
        ", possibly more — the page filled before a pre-cursor update"
        if au.get("possibly_more")
        else ""
    )
    out.append(f"== 8. merged since the cursor: {len(au['items'])} · since {since}")
    for it in au["items"]:
        out.append(
            f"  #{it['number']} {it['verdict']} · landed `{(it.get('landed') or '?')[:9]}` "
            f"at merge `{(it.get('merge') or '?')[:9]}` · carry={it['carry']} · {it['merged_at']}"
        )
        out += [f"      ERROR merged: {e}" for e in it["errors"]]
    out += _errors("merged", au)
    return "\n".join(out) + "\n"


# --- CLI ------------------------------------------------------------------------------------


def _since_arg(text: str) -> datetime:
    try:
        return parse_time(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"not an ISO UTC time: {text!r}") from exc


def _repo_arg(text: str) -> str:
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", text):
        raise argparse.ArgumentTypeError(f"not OWNER/REPO: {text!r}")
    return text


def main(
    argv: Sequence[str] | None = None,
    runner: Runner = run_command,
    clock: Clock = utc_now,
) -> int:
    parser = argparse.ArgumentParser(
        prog="scripts/uplevel/coordinator_snapshot.py",
        description="Read the coordinator's tick state in one call (read-only).",
    )
    parser.add_argument("--repo", type=_repo_arg, default=DEFAULT_REPO)
    parser.add_argument("--since", type=_since_arg, help="override the heartbeat cursor (ISO UTC)")
    parser.add_argument("--json", action="store_true", help="print JSON instead of text")
    args = parser.parse_args(argv)
    data = Snapshot(args.repo, runner, clock, args.since).build()
    if args.json:
        sys.stdout.write(json.dumps(data, indent=1) + "\n")
    else:
        sys.stdout.write(render_text(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
