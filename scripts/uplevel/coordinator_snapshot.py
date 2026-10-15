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
4. legs       - UR-102's three no-update-branch legs for each non-draft PR with a green gate,
                measured from the `main` its gate's run merged the head into (read from that
                run's checkout log), else from the merge-base, labelled as a fallback;
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
MAX_MERGES_BEHIND = 3
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
# actions/checkout in a pull_request run prints the merge it tested; the second sha is the
# `main` the run ran against. The run API's pull_requests[0].base.sha is the PR's stored base,
# which a later push does not move, so it is not that sha.
CHECKOUT_MERGE = re.compile(r"HEAD is now at [0-9a-f]+ Merge ([0-9a-f]{40}) into ([0-9a-f]{40})")
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

CHECKOUT_JOBS_JQ = (
    '[.jobs[] | select(.conclusion == "success" and any(.steps[]?; .name | test("checkout"; "i")))'
    " | {id, steps: (.steps | length)}]"
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


def issue_number(comment: dict[str, Any]) -> int | None:
    url = comment.get("issue_url") or ""
    tail = url.rstrip("/").rsplit("/", 1)[-1]
    return int(tail) if tail.isdigit() else None


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

    # 5. main (read before the PRs: UR-102's third leg needs it) -----------------------------

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

    # 3-4. PRs and merge legs ---------------------------------------------------------------

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
        if item["gate"] == "SUCCESS" and item["merge_base"]:
            self._legs(item)
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
        own["carry"] = own["head"] == own["approved"]

    def _hash_own(
        self,
        item: dict[str, Any],
        root: str,
        rev: str,
        files: list[str],
        own: dict[str, Any],
    ) -> str | None:
        """``sha256`` of the rev's own diff at its own merge-base, or None with an error named
        ``own-diff`` -- a failed read must never read as a carry (UR-106, UR-154)."""
        try:
            base = self.git("merge-base", root, rev)
            diff = self.run(["git", "diff", f"{base}..{rev}", "--", *files])
        except Exception as exc:  # reported, not fatal; carry stays None
            item["errors"].append(f"own-diff {rev[:9]}: {error_text(exc)}")
            own["reads"] += 1
            return None
        own["reads"] += 1
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

    def run_base(self, run_id: int | None, head: str) -> str:
        """The `main` sha the gate's run merged the head into, read from a checkout job's log."""
        if run_id is None:
            raise ValueError("no run id in the gate's detailsUrl")
        jobs = self.gh_paginated(
            f"repos/{self.repo}/actions/runs/{run_id}/jobs?per_page=100", "--jq", CHECKOUT_JOBS_JQ
        )
        if not jobs:
            raise ValueError(f"run {run_id} has no successful checkout job")
        job = min(jobs, key=lambda j: j["steps"])  # the shortest job has the shortest log
        log = self.run(["gh", "api", f"repos/{self.repo}/actions/jobs/{job['id']}/logs"])
        match = CHECKOUT_MERGE.search(log)
        if not match:
            raise ValueError(f"job {job['id']} log names no checkout merge")
        if match.group(1) != head:
            raise ValueError(f"run {run_id} tested {match.group(1)[:9]}, not the head")
        return match.group(2)

    def _legs(self, item: dict[str, Any]) -> None:
        head = item["head"]
        legs: dict[str, Any] = {}
        item["legs"] = legs
        basis: dict[str, Any] = {"run_id": item.get("gate_run"), "merge_base": item["merge_base"]}
        item["leg_base"] = basis
        try:
            basis["run_base"] = self.run_base(item.get("gate_run"), head)
            basis["used"] = "run"
        except Exception as exc:  # fall back to the merge-base, and say so
            basis["run_base"] = None
            basis["used"] = "merge-base fallback"
            basis["error"] = error_text(exc)
        base = basis["run_base"] or item["merge_base"]
        try:
            behind = int(self.git("rev-list", "--count", "--first-parent", f"{base}..origin/main"))
            legs["behind"] = {"merges": behind, "pass": behind <= MAX_MERGES_BEHIND}
        except Exception as exc:  # reported, not fatal
            legs["behind"] = {"error": error_text(exc), "pass": False}
        try:
            main_files = set(self.git("diff", "--name-only", base, "origin/main").splitlines())
            # The PR's own files come from its merge-base: a run base newer than the merge-base
            # is not an ancestor of the head, and a diff from it would add main's changes.
            own = item["merge_base"]
            pr_files = set(self.git("diff", "--name-only", own, head).splitlines())
            shared = sorted(main_files & pr_files)
            legs["overlap"] = {"paths": shared, "pass": not shared}
        except Exception as exc:  # reported, not fatal
            legs["overlap"] = {"error": error_text(exc), "pass": False}
        red = self.main_red()
        last = self.data["main"].get("ci_last_completed")
        legs["main_ci"] = {
            "conclusion": last["conclusion"] if last else None,
            "pass": red is False,
        }
        item["merge_without_update"] = all(leg["pass"] for leg in legs.values())

    # 6. heartbeats ---------------------------------------------------------------------------

    def _heartbeats(self, heartbeat_comments: list[dict[str, Any]] | Exception) -> None:
        section: dict[str, Any] = {"items": [], "errors": []}
        self.data["heartbeats"] = section
        if isinstance(heartbeat_comments, Exception):
            section["errors"].append(error_text(heartbeat_comments))
            return
        for c in heartbeat_comments:
            body = (c.get("body") or "").lstrip()
            if not body.startswith(HEARTBEAT_PREFIX):
                continue
            agent = body[len(HEARTBEAT_PREFIX) :].split("-->", 1)[0].strip()
            age = (self.now - parse_time(c["updated_at"])).total_seconds() / 60
            head_lines = "\n".join(body.splitlines()[:3]).lower()
            section["items"].append(
                {
                    "agent": agent,
                    "id": c.get("id"),
                    "updated_at": c["updated_at"],
                    "age_min": round(age, 1),
                    "paused": is_paused(head_lines),
                    "stale": age > STALE_HEARTBEAT_MIN,
                }
            )


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
            out.append(
                f"      own-diff head={_hash_txt(head_h)} approved={_hash_txt(appr_h)}"
                f" carry={txt}" + (f" ({own['error']})" if own.get("error") else "")
            )
        out += [f"      ERROR prs: {e}" for e in p["errors"]]
    out += _errors("prs", prs)

    out.append("== 4. merge legs (UR-102), non-draft PRs with a green gate")
    any_legs = False
    for p in prs["items"]:
        legs = p.get("legs")
        if not legs:
            continue
        any_legs = True
        b, o, m = legs["behind"], legs["overlap"], legs["main_ci"]
        b_txt = b.get("error") or f"{b['merges']} merges"
        basis = p["leg_base"]
        if basis["used"] == "run":
            base_txt = f"base: run {basis['run_base'][:9]} (run {basis['run_id']})"
        else:
            base_txt = f"(base: merge-base fallback) run base unread: {basis['error']}"
        out.append(f"  #{p['number']} {base_txt} · merge-base {(basis['merge_base'] or '?')[:9]}")
        o_txt = o.get("error") or (", ".join(o["paths"][:5]) or "none")
        out.append(
            f"      behind {'PASS' if b['pass'] else 'FAIL'} ({b_txt}) · "
            f"overlap {'PASS' if o['pass'] else 'FAIL'} ({o_txt}) · "
            f"main CI {'PASS' if m['pass'] else 'FAIL'} ({m['conclusion']}) → "
            f"merge without update-branch: {'yes' if p['merge_without_update'] else 'no'}"
        )
    if not any_legs:
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
            flags.append(f"STALE >{STALE_HEARTBEAT_MIN}m")
        flag = f" [{', '.join(flags)}]" if flags else ""
        out.append(f"  {h['agent']} {h['updated_at']} age {h['age_min']}m id={h['id']}{flag}")
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
