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
3. prs        - each open PR: head, merge-base, mergeStateStatus, ``CI Gate`` at the head, and the
                newest ``Review: approve`` comment's sha against the head (UR-106);
4. legs       - UR-102's three no-update-branch legs for each non-draft PR with a green gate,
                measured from the `main` its gate's run merged the head into (read from that
                run's checkout log), else from the merge-base, labelled as a fallback;
5. main       - tip, CI (UR-111), Deploy, Nightly Full Gate and Flaky Test Detection (UR-116);
6. heartbeats - every ``<!-- heartbeat:`` comment on #6958, its age and ``paused`` (UR-38, UR-160),
                flagged when older than 20 minutes (UR-162).

It never writes to GitHub. A failed ``gh`` or ``git`` call prints ``ERROR <section>: <message>``
in its section and the report goes on; the exit code is 0 unless the arguments are invalid.
Every subprocess call goes through one ``Runner`` so the tests replace it without a network.
"""

from __future__ import annotations

import argparse
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
        cmd = [
            "gh", "pr", "list", "--repo", self.repo, "--state", "open", "--limit", "200",
            "--json", "number,title,isDraft,labels,headRefOid,mergeStateStatus,statusCheckRollup",
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
            section["items"].append(self._pr_item(pr))

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
                '[.[] | select(.body | startswith("Review:"))'
                " | {id, created_at, user: .user.login, body}]",
            )
        except Exception as exc:  # reported, not fatal
            item["errors"].append(f"reviews: {error_text(exc)}")
            return
        reviews.sort(key=lambda r: r.get("created_at") or "")
        if reviews:
            item["latest_review"] = truncate(first_line(reviews[-1]["body"]), 60)
        approvals = [r for r in reviews if is_approval(first_line(r["body"]))]
        if not approvals:
            item["approval"] = None
            return
        newest = approvals[-1]
        sha = approval_sha(newest["body"])
        item["approval"] = {
            "id": newest["id"],
            "by": newest.get("user"),
            "sha": sha,
            "matches_head": bool(sha) and item["head"].startswith(sha),
        }

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
        out.append(line)
        labels = ",".join(p["labels"]) or "-"
        out.append(f"      {p['title']} [{labels}]")
        if p.get("latest_review") and not is_approval(p["latest_review"]):
            out.append(f"      latest review: {p['latest_review']}")
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
