#!/usr/bin/env python3
"""Update the next queued PR when ``main`` moves (ruling 272; record 6282551725).

    uv run python -m scripts.uplevel.queue_update --repo OWNER/REPO [--dry-run]

One fire of ``.github/workflows/queue-update.yml`` reads the coordinator's queue line from the
status comment on the ruling issue, ``main``'s tip and the newest completed ``CI`` run on
``main``, then acts on at most one entry -- exactly ruling 272 item 3's seven steps:

1. **Reads** the queue line, ``main``'s tip and the newest completed ``CI`` run on ``main``.
2. **In flight**: a listed PR that is open, not behind ``main`` and whose gate has not failed
   does nothing this fire.
3. **Red ``main``**: when ``main``'s newest completed ``CI`` run failed, only a ``!`` entry
   acts; every other entry is left to the coordinator (UR-111).
4. **Skips** an entry that is merged, closed or a draft, or whose UR-106 own-diff carry at its
   head says no -- ``coordinator_snapshot.ur106_diff_hash`` equal-hash short-circuit, else
   ``ur106_subset_carry`` (ruling 278): update-branch merges only between the heads, the new
   diff a subset of the approved one, and ``main``'s own change between the merge-bases
   holding every dropped line. An author commit drops the entry, an update merge keeps it,
   and a failed read is unknown -- the entry stays queued (UR-154).
5. **Updates** the first remaining entry that is behind ``main``, and only that one:
   ``PUT repos/<repo>/pulls/<n>/update-branch`` with ``expected_head_sha``, then arms
   auto-merge. A conflicting update falls through to the next entry in the same fire.
6. **Re-judges the carry**: a carry that turned no across the update disarms auto-merge and
   leaves the PR to the coordinator.
7. **Comments once** on the PR it updated -- old and new head, ``main``'s tip, the two
   own-diff hashes and the run link -- and every fire writes a job summary saying what it
   saw, even when it did nothing.

The job's ``GITHUB_TOKEN`` is read-only for contents (``issues: write`` lets the step-7
comment POST ride it); ``QUEUE_UPDATE_TOKEN`` is a per-call auth override on exactly the
ruling-named writes -- the ``update-branch`` PUT and the auto-merge arm/disable mutation.
The workflow never checks out or runs a PR's code. Everything this module reads and writes
arrives through one injectable runner, so the tests need no network and patch nothing;
``--dry-run`` prints the plan and calls nothing.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coordinator_snapshot as snap  # sibling: ur106_diff_hash, the ruling issue, CommandError

# The runner carries stdin too (``run(cmd, stdin)``) -- update-branch's PUT body rides it,
# the way ``post_record.run_with_input`` does; a body that only lived in a local variable
# would never reach the API.
Runner = Callable[[Sequence[str], str], str]

OWNER_ISSUE = snap.OWNER_ISSUE  # the status comment lives on the owner/ruling issue (#6854)
DEFAULT_REPO = snap.DEFAULT_REPO  # never guessed (memory: gh-repo-slug)
QUEUE_LINE = re.compile(r"<!--\s*queue:\s*(.*?)\s*-->")
ENTRY = re.compile(r"(!?)(\d+)@([0-9a-fA-F]{9,40})")
QUEUE_COMMENT_MARKER = "<!-- status:uplevel-coordinator"
SUMMARY_LINES = 80  # the job summary caps itself, a digest-length read for the tick


def _rest_path(repo: str, tail: str) -> str:
    return f"repos/{repo}/{tail}"


@dataclass
class Entry:
    """One parsed queue entry: ``!`` prefix (UR-111), PR number, the coordinator-judged sha."""

    urgent: bool
    number: int
    sha: str

    def render(self) -> str:
        return f"{'!' if self.urgent else ''}{self.number}@{self.sha[:9]}"


@dataclass
class EntryState:
    """What one fire read about a listed entry, in the order item 3 asks it."""

    entry: Entry
    state: str | None = None  # GitHub's state field: open | closed | merged
    draft: bool = False
    behind: bool | None = None  # None: unread (a failed read never reads as "not behind")
    gate_failed: bool | None = None  # None: unread
    head: str | None = None
    errors: list[str] = field(default_factory=list)


@dataclass
class Plan:
    """What one fire decided -- the job summary and the dry-run print both render this."""

    main_tip: str | None = None
    main_ci_conclusion: str | None = None
    queue_entries: list[Entry] = field(default_factory=list)
    read_errors: list[str] = field(default_factory=list)
    entries: list[EntryState] = field(default_factory=list)
    action: str = "none"  # none | no-op | update | conflict-fallthrough
    acted_entry: int | None = None
    action_note: str = ""


def parse_queue_line(body: str) -> list[Entry]:
    """The queue line's entries, in order, or [] for an empty/missing line (item 2's shape).

    ``<!-- queue: -->`` and a body with no line at all both read as an empty queue -- the
    coordinator wrote "nothing ready" either way, and item 3's "reads the queue line" asks
    for the entries, not for the comment.
    """
    m = QUEUE_LINE.search(body)
    if not m:
        return []
    entries: list[Entry] = []
    for token in m.group(1).split():
        em = ENTRY.fullmatch(token)
        if em is None:
            continue  # a malformed token is skipped, not fatal: the rest of the queue stands
        entries.append(Entry(urgent=em.group(1) == "!", number=int(em.group(2)), sha=em.group(3)))
    return entries


def find_status_comment(comments: list[dict]) -> dict | None:
    """The newest comment that opens with the status marker -- the one whose body the
    coordinator keeps current. A comment that merely contains the marker elsewhere is not
    the status comment."""
    marked = [c for c in comments if c.get("body", "").startswith(QUEUE_COMMENT_MARKER)]
    return marked[-1] if marked else None


def _run(run: Runner, *cmd: str, stdin: str = "") -> str:
    return run(["gh", "api", *cmd], stdin)


def _auth(token: str | None) -> list[str]:
    """The per-call auth override for the write credential: an empty list when no token is
    set (gh's ambient auth rides instead -- the tests' fake, or a dry run), else the header
    that makes THIS call use ``QUEUE_UPDATE_TOKEN`` while every other call keeps the job's
    read-only ``GH_TOKEN``. Ruling 272 item 3 bounds the secret to exactly its two calls:
    ``update-branch`` and the auto-merge arm/disable mutation."""
    return ["-H", f"Authorization: token {token}"] if token else []


class _GhRestError(Exception):
    """A ``gh api`` write call exited non-zero, CARRYING its stdout with it.

    ``real_run`` raises on a non-zero exit and discards stdout -- but ``gh api --include``
    prints the HTTP status line on STDOUT even when it exits 1 (every HTTP >= 400 exits 1),
    so the status the caller must parse (409 conflict, 422 mismatch, 500 boom) lives in the
    exception, not in a return value. Catching the bare exception and treating stdout as
    empty read every such answer as status 0 (N10): the conflict branch stayed unreachable
    in production while the fake, whose contract is stdout-carrying, passed. The runner
    contract here is therefore: an HTTP-answered call raises ``_GhRestError`` with
    ``stdout`` set; a transport death (no answer at all) raises anything else.
    """

    def __init__(self, message: str, stdout: str = "") -> None:
        super().__init__(message)
        self.stdout = stdout


class _CarryingError(snap.CommandError):
    """``real_run``'s raise, with the process stdout attached for ``_gh_rest`` to read."""

    stdout: str


def _gh_rest(
    run: Runner, method: str, path: str, stdin: str = "", token: str | None = None
) -> tuple[int, dict | list]:
    """A REST call answered with its HTTP status and parsed body -- update-branch answers 202
    and a conflict 409 (the ``expected_head_sha`` mismatch class is 422), all of which the
    caller must tell apart. ``stdin`` is the request body (the PUT's JSON), fed through the
    runner's stdin channel; ``token`` overrides the auth for this one call (the write
    credential's two calls only).

    The status survives BOTH of gh's failure shapes: an HTTP >= 400 answer exits 1 with the
    ``--include`` status line on stdout -- the runner raises, so a raising runner must carry
    its stdout (``_GhRestError``; ``real_run`` wraps it) -- while a transport death answers
    with nothing at all and reads as status 0, which is not any branch's shape (N10: the
    swallowed-stdout shape read every conflict as 0)."""
    try:
        out = run(
            ["gh", "api", "-X", method, path, *_auth(token), "--input", "-", "--include"], stdin
        )
    except snap.CommandError as exc:
        carried = getattr(exc, "stdout", None)
        out = carried if isinstance(carried, str) else ""
    except _GhRestError as exc:  # a test fakes the raising contract directly
        out = exc.stdout
    except Exception:
        out = ""
    # `gh api --include` prints the headers, a blank line, then the body; the status is the
    # first line's second token.
    head, _, body = out.partition("\r\n\r\n")
    if not head:
        head, _, body = out.partition("\n\n")
    status = 0
    if head:
        first = head.splitlines()[0]
        parts = first.split()
        if len(parts) >= 2 and parts[1].isdigit():
            status = int(parts[1])
    try:
        parsed = json.loads(body) if body.strip() else {}
    except json.JSONDecodeError:
        parsed = {}
    return status, parsed


def read_state(
    run: Runner, repo: str, issue: int
) -> tuple[list[Entry], str, str | None, list[str]]:
    """Item 3 step 1: the queue entries, ``main``'s tip and the newest completed ``CI`` run's
    conclusion on ``main`` -- plus every read error, which the caller reports, never swallows
    (a failed read must not read as "all clear", UR-154's shape)."""
    errors: list[str] = []
    try:
        # `--paginate`: the status comment the coordinator edits in place (UR-25) slides
        # deeper as #6854 grows -- it sits on page 5 of 9 today (893 comments), so a
        # single-page read would see an empty queue every fire. The house precedent is
        # Coordinator.gh_paginated (coordinator_snapshot.py), which streams one JSON value
        # per page and flattens arrays.
        comments = snap.parse_json_stream(
            _run(run, f"{_rest_path(repo, f'issues/{issue}/comments')}?per_page=100", "--paginate")
        )
    except Exception as exc:  # reported, not fatal: an unread queue is an empty plan
        return [], "", None, [f"queue-line read: {snap.error_text(exc)}"]
    comment = find_status_comment(comments if isinstance(comments, list) else [])
    body = (comment or {}).get("body", "")
    entries = parse_queue_line(body)
    tip = _main_tip(run, repo, errors)
    conclusion = _main_ci_conclusion(run, repo, errors)
    return entries, tip, conclusion, errors


def _main_tip(run: Runner, repo: str, errors: list[str]) -> str:
    try:
        answer = json.loads(_run(run, _rest_path(repo, "commits/main")))
        return str(answer.get("sha") or "")
    except Exception as exc:
        errors.append(f"main tip: {snap.error_text(exc)}")
        return ""


def _main_ci_conclusion(run: Runner, repo: str, errors: list[str]) -> str | None:
    """The newest completed ``CI`` run on ``main``: its conclusion, or None while none is
    completed (in-flight main counts as neither red nor green).

    The read is the CI workflow's OWN runs (``actions/workflows/ci.yml/runs``), not the
    runs listing: REST's ``actions/runs`` endpoint has no ``workflow`` filter, so a
    ``workflow=CI`` query there returns the newest completed run of ANY workflow (r288:
    on a red main whose newest run was a green plumbing job, the plan read "success" and
    the ``!`` filter never fired)."""
    try:
        runs = json.loads(
            _run(
                run,
                _rest_path(
                    repo,
                    "actions/workflows/ci.yml/runs?branch=main&status=completed&per_page=1",
                ),
            )
        )
        runs_list = runs.get("workflow_runs") or []
        conclusion = runs_list[0].get("conclusion") if runs_list else None
        return str(conclusion) if conclusion is not None else None
    except Exception as exc:
        errors.append(f"main CI read: {snap.error_text(exc)}")
        return None


def read_entry(run: Runner, repo: str, state: EntryState, main_tip: str) -> EntryState:
    """What one listed entry looks like right now: state, draft flag, head, and whether it is
    behind ``main`` and its gate has failed there. Every failed read is reported into the
    entry's ``errors`` and leaves its field None -- a failed read never reads as a decision
    (the _hash_own precedent: ``carry`` stays None on a read error)."""
    n = state.entry.number
    try:
        pr = json.loads(_run(run, _rest_path(repo, f"pulls/{n}")))
        state.state = str(pr["state"]) if pr.get("state") is not None else None
        state.draft = bool(pr.get("draft"))
        sha = pr.get("head", {}).get("sha")
        state.head = str(sha) if sha is not None else None
    except Exception as exc:
        state.errors.append(f"pr read: {snap.error_text(exc)}")
        return state
    if state.head is None:
        state.errors.append("pr read: the head sha is missing")
        return state
    state.behind = _behind(run, repo, n, main_tip, state.errors)
    state.gate_failed = _gate_failed(run, repo, state.head, state.errors)
    return state


def _behind(run: Runner, repo: str, number: int, main_tip: str, errors: list[str]) -> bool | None:
    """The PR's base sha differs from ``main``'s tip. Comparing the BASE sha -- the sha the
    PR's branch forks from -- is the behind-test: an update-branch sets it to ``main``'s tip
    (the merge commit's sha), and a PR merged to an older ``main`` stays behind until it is
    updated. The empty tip (a failed read) answers None: not-a-decision."""
    if not main_tip:
        return None
    try:
        pr = json.loads(_run(run, _rest_path(repo, f"pulls/{number}")))
        base = pr.get("base", {}).get("sha")
        return None if base is None else base != main_tip
    except Exception as exc:
        errors.append(f"behind read: {snap.error_text(exc)}")
        return None


def _gate_failed(run: Runner, repo: str, head: str, errors: list[str]) -> bool | None:
    """Whether the head's newest ``CI Gate (Required Checks)`` check has failed -- item 3
    step 2's "its ``CI Gate`` at its head has not failed". Only a FAILED conclusion reads as
    failed: in-flight, skipped and neutral legs are not a failure (the digest's own reading),
    and None means the read itself failed. With no gate check present at all the gate has not
    failed (it has not finished)."""
    try:
        runs = json.loads(_run(run, _rest_path(repo, f"commits/{head}/check-runs?per_page=100")))
    except Exception as exc:
        errors.append(f"gate read: {snap.error_text(exc)}")
        return None
    checks = runs.get("check_runs") or []
    gate = [c for c in checks if c.get("name") == "CI Gate (Required Checks)"]
    # One required check, UR-119 -- its conclusion is the gate's.
    if not gate:
        return False
    return str(gate[0].get("conclusion")) == "failure"


def _own_diff_files(run: Runner, repo: str, number: int, errors: list[str]) -> list[str] | None:
    """The PR's own paths, bounding the UR-106 hash to the PR (the _pr_files precedent)."""
    try:
        files = json.loads(_run(run, _rest_path(repo, f"pulls/{number}/files?per_page=100")))
        return [f["filename"] for f in files if f.get("filename")]
    except Exception as exc:
        errors.append(f"own-diff files: {snap.error_text(exc)}")
        return None


def _hash_at(
    run: Runner,
    repo: str,
    number: int,  # named for the caller's shape; the hash is rev-keyed
    rev: str,
    root: str,
    files: list[str],
    errors: list[str],
) -> str | None:
    """The UR-106 own-diff hash of one rev (the ruling-278 subset path keeps the diff, so
    this thin wrapper names the hash-only consumers: _comment_update's rendering)."""
    got = _diff_at(run, repo, number, rev, root, files, errors)
    return None if got is None else got.hash


@dataclass
class _RevDiff:
    """One rev's own-diff read: the UR-106 hash, the diff TEXT the subset rule's line
    multisets need (the hash throws the lines away), and the rev's merge-base with
    ``root`` -- the subset condition 3 diffs ``main``'s own change BETWEEN the two
    merge-bases, so both bases must survive the read. ``rev`` is the expanded full sha
    (the queue line lists a 9-char prefix git cannot fetch)."""

    hash: str
    diff: str
    base: str
    rev: str


def _diff_at(
    run: Runner,
    repo: str,
    number: int,  # named for the caller's shape; the read is rev-keyed
    rev: str,
    root: str,
    files: list[str],
    errors: list[str],
) -> _RevDiff | None:
    """The UR-106 own-diff read of one rev, hashed against ITS OWN merge-base with
    ``root`` (``main``'s fresh tip) -- the _hash_own precedent, per-rev: hashing both revs
    against one shared base would report carry=no for a roll that carries.

    The base comes from the server-side three-dot compare (``compare/<root>...<rev>``
    answers ``merge_base_commit``), and both revs are fetched at depth 1 before the diff:
    the workflow's checkout is ``fetch-depth: 1``, so the old ``git merge-base`` had no
    graph to walk (r5 B3) -- and its stdout rode UNSTRIPPED into the range arg, a trailing
    newline making ``git diff`` exit 128 so no hash was ever produced (r5 B1). No
    merge-base call remains: a compare read answers the base as a bare sha, and the fetch
    and the diff both take sha arguments only. The queue line lists a 9-char prefix, which
    git cannot fetch, so the rev is expanded through a ``commits/<rev>`` read first (an
    ambiguous or missing prefix errors here -- not-a-carry, never a guess). The paths ride
    as ``:(literal)`` pathspecs: a PR-controlled filename like ``:(exclude)**`` would
    otherwise rewrite the diff's pathspec and read as an empty diff -- equal hashes, a
    false carry (n4; the coordinator's _hash_own carries the same guard).

    Ruling 278: the diff TEXT and the merge-base ride back with the hash so the subset
    path can decide a carry the hash cannot (an update-branch merge of main between the
    listed sha and the head that keeps the diff a subset of what was approved); a caller
    that needs only the hash reads it off ``.hash`` unchanged."""
    try:
        if len(rev) < 40:
            rev = str(json.loads(_run(run, _rest_path(repo, f"commits/{rev}")))["sha"])
        answer = json.loads(_run(run, _rest_path(repo, f"compare/{root}...{rev}")))
        base = str((answer.get("merge_base_commit") or {}).get("sha") or "")
        if not base:
            raise ValueError("the compare answered no merge base")
        run(["git", "fetch", "--quiet", "--depth", "1", "origin", base, rev], "")
        diff = run(["git", "diff", f"{base}..{rev}", "--", *(f":(literal){f}" for f in files)], "")
    except Exception as exc:
        errors.append(f"own-diff {rev[:9]}: {snap.error_text(exc)}")
        return None
    return _RevDiff(snap.ur106_diff_hash(diff), diff, base, rev)


def _chain_between(
    run: Runner, repo: str, left: str, right: str, errors: list[str]
) -> list[list[str]] | None:
    """The first-parent commits after ``left`` up to ``right``, as parent lists, read off
    the server-side three-dot compare ``compare/<left>...<right>`` (the depth-1 checkout
    has no graph to walk; the compare's ``commits[]`` names every commit reachable from
    ``right`` but not ``left``, each with its parents). REST gives no ``--first-parent``,
    so the chain is RECONSTRUCTED: walk ``parents[0]`` from ``right`` back to ``left``
    through a sha->commit map -- every commit on that walk is reachable-from-right and
    not-from-left, so it must sit in the answer; a missing sha (a shallow race or the
    compare's 250-commit page cap) is a failed read, not a guess. Returns None when the
    walk cannot complete."""
    try:
        answer = json.loads(_run(run, _rest_path(repo, f"compare/{left}...{right}")))
        by_sha = {str(c.get("sha")): c for c in answer.get("commits") or [] if c.get("sha")}
        chain: list[list[str]] = []
        cur = right
        while cur != left:
            commit = by_sha.get(cur)
            if commit is None:
                raise ValueError(f"the compare answered no commit {cur[:9]} on the walk")
            chain.append([str(p["sha"]) for p in commit.get("parents") or []])
            parents = chain[-1]
            if not parents:
                raise ValueError(f"the compare answered no parents for {cur[:9]}")
            cur = parents[0]
        return chain
    except Exception as exc:
        errors.append(f"subset chain: {snap.error_text(exc)}")
        return None


def _subset_carry(
    run: Runner,
    repo: str,
    number: int,
    left: _RevDiff,
    right: _RevDiff,
    root: str,
    files: list[str],
    errors: list[str],
) -> bool | None:
    """Ruling 278's subset carry over the queue's REST seams, decided by the snapshot's
    own function (one decision, box 2: the queue's skip and disarm steps use the same
    rule the snapshot's §3 and §7/§8 verdicts use). ``left`` is the listed/approved rev's
    read, ``right`` the head's; ``root`` is ``main``'s tip and ``files`` the PR's own-diff
    files, both already in the caller's hand. The three conditions read through:

    - condition 1 (every commit after the approved head is an update-branch merge of
      main): the reconstructed first-parent chain, each merge's second parent checked
      with the two-dot compare ``compare/<p2>...<main tip>`` -- the answered merge base
      equals ``p2`` iff p2 sits on ``main``. A two-dot compare, not three-dot: the
      three-dot base IS a merge base, itself an ancestor of the head, so ``status``
      could never read diverged for the right reason.
    - condition 2 (N contained in A as a multiset) and condition 3 (every line in A but
      not in N appears, same file and sign, in main's own change between the two
      merge-bases): the kept diff texts and per-rev merge-bases feed
      ``snap.ur106_subset_carry``; the between-bases diff is read with the same
      sha-args-only contract (``git diff <base>..<base>``), fetched at depth 1 only when
      the two bases differ.

    Every failed or ambiguous read returns None -- unknown, never yes and never no
    (UR-154)."""
    chain = _chain_between(run, repo, left.rev, right.rev, errors)
    if chain is None:
        return None

    def on_main(parent: str) -> bool | None:
        try:
            answer = json.loads(_run(run, _rest_path(repo, f"compare/{parent}...{root}")))
            base = str((answer.get("merge_base_commit") or {}).get("sha") or "")
            if not base:
                raise ValueError("the compare answered no merge base")
            return base == parent  # the merge base of p2 and the tip is p2 iff p2 on main
        except Exception as exc:
            errors.append(f"on-main {parent[:9]}: {snap.error_text(exc)}")
            return None

    def main_change() -> str | None:
        try:
            if left.base != right.base:
                run(
                    ["git", "fetch", "--quiet", "--depth", "1", "origin", left.base, right.base],
                    "",
                )
            return run(
                [
                    "git",
                    "diff",
                    f"{left.base}..{right.base}",
                    "--",
                    *(f":(literal){f}" for f in files),
                ],
                "",
            )
        except Exception as exc:
            errors.append(f"main between bases: {snap.error_text(exc)}")
            return None

    verdict, _lines, _why = snap.ur106_subset_carry(
        left.diff, right.diff, chain, main_change, on_main
    )
    if verdict is None:
        errors.append("subset carry: a read failed -- unknown, never a fact")
    return verdict


def decide(
    run: Runner, repo: str, plan: Plan, issue: int
) -> Plan:  # issue kept for the write path's shape
    """Steps 2-4: read every entry, then pick the action. At most one entry acts per fire.

    The skip ladder, in item 3's order: merged/closed/draft, a None behind-read (unread --
    not-a-decision), gate failed, own-diff carry no (hash mismatch the subset rule confirms,
    ruling 278), not behind. Red ``main`` filters the
    queue to ``!`` entries before any of it (step 3). A None gate-read also passes the skip
    (not-a-failure), but the update itself re-reads the gate no -- None stays out of the write
    path where a decision is needed.
    """
    red_main = plan.main_ci_conclusion == "failure"
    if red_main:
        kept = [e for e in plan.queue_entries if e.urgent]
        plan.action_note = "red main: acting only on ! entries (UR-111)"
    else:
        kept = list(plan.queue_entries)
    for entry in kept:
        st = EntryState(entry=entry)
        read_entry(run, repo, st, plan.main_tip or "")
        plan.entries.append(st)
    for st in plan.entries:
        if st.state in ("merged", "closed") or st.draft:
            continue
        if st.behind is None or st.gate_failed is None:
            continue  # a failed read is not a decision: skip, and say so in the summary
        if st.gate_failed:
            continue
        if not st.behind:
            continue  # not behind: nothing to update (step 2's in-flight shape)
        files = _own_diff_files(run, repo, st.entry.number, st.errors)
        if files is None:
            continue
        listed = _diff_at(
            run, repo, st.entry.number, st.entry.sha, plan.main_tip or "", files, st.errors
        )
        if st.head is None:
            continue  # no head, no hash: unhashable, skip (read_entry reports it)
        head = _diff_at(run, repo, st.entry.number, st.head, plan.main_tip or "", files, st.errors)
        if listed is None or head is None:
            continue  # an unhashable diff is not a carry: skip, never guess
        if listed.hash == head.hash:
            plan.action = "update"
            plan.acted_entry = st.entry.number
            plan.action_note = (
                f"updating #{st.entry.number} ({st.entry.sha[:9]} -> main "
                f"{plan.main_tip[:9] if plan.main_tip else ''})"
            )
            return plan
        # the hashes differ (ruling 278): not every hash difference is an author commit.
        # An update-branch merge of main between the listed sha and the head can carry
        # the own diff as a subset of what was approved -- the subset rule decides, and
        # unknown (a failed read) keeps the entry queued, never dropped on a guess.
        carried = _subset_carry(
            run,
            repo,
            st.entry.number,
            listed,
            head,
            plan.main_tip or "",
            files,
            st.errors,
        )
        if carried is True:
            plan.action = "update"
            plan.acted_entry = st.entry.number
            plan.action_note = (
                f"updating #{st.entry.number} ({st.entry.sha[:9]} -> main "
                f"{plan.main_tip[:9] if plan.main_tip else ''}; subset carry)"
            )
            return plan
        if carried is None:
            continue  # unknown: not-a-decision, the entry stays queued
        continue  # carried is False: an author commit changed the own diff; the entry drops
    if plan.queue_entries:
        plan.action = "no-op"
    return plan


def act(
    run: Runner,
    repo: str,
    plan: Plan,
    token: str | None,
    run_url: str = "",
) -> Plan:
    """Steps 5-7: the one write fire. ``token`` is ``QUEUE_UPDATE_TOKEN``; with it absent
    (dry-run, or the secret unset) nothing is written and the plan says so."""
    if plan.action != "update" or plan.acted_entry is None:
        return plan
    n = plan.acted_entry
    st = next(s for s in plan.entries if s.entry.number == n)
    if not token:
        plan.action_note = "no token: dry-run, nothing written"
        return plan
    body = {"expected_head_sha": st.head, "update_method": "merge"}
    status, answer = _gh_rest(
        run, "PUT", _rest_path(repo, f"pulls/{n}/update-branch"), json.dumps(body), token
    )
    if status in (409, 422):
        # A conflict falls through to the next entry in the SAME fire (step 5). The
        # fallthrough lives in fire(): this fire re-decides with this entry marked skipped.
        # GitHub's REST reference documents 202/403/422 for update-branch, and names 422
        # as the expected_head_sha-mismatch class. 409 is kept in the conflict set as
        # defense against undocumented codes -- both read as "this entry cannot update now".
        plan.action = "conflict-fallthrough"
        plan.action_note = (
            f"update of #{n} conflicted ({status}): falling through to the next entry"
        )
        st.errors.append(f"update-branch conflicted ({status})")
        return plan
    if status not in (200, 202):
        plan.action_note = f"update-branch answered {status}: nothing more this fire"
        st.errors.append(f"update-branch answered {status}: {json.dumps(answer)[:200]}")
        return plan
    new_head = _post_update_head(run, repo, n, st)
    _arm_auto_merge(run, repo, n, st, token)
    carried = _carry_check(run, repo, st, new_head, plan.main_tip or "")
    if carried is False:
        _disarm_auto_merge(run, repo, n, st, token)
        plan.action_note = (
            f"#{n} updated to {new_head[:9] if new_head else '?'}; own diff changed "
            "(carry: no) -- auto-merge disarmed, left to the coordinator"
        )
    else:
        plan.action_note = (
            f"#{n} updated {st.entry.sha[:9]} -> {new_head[:9] if new_head else '?'}; "
            f"auto-merge armed; carry: {'yes' if carried else 'unread'}"
        )
    # Step 7 comments once on the PR it updated -- after an update, either way. Item 6 makes
    # this comment the own-diff comparison UR-106's condition 1 asks the coordinator to
    # quote, and the carry:no handoff is exactly where the coordinator reads it on the PR
    # (the job summary is not that channel).
    _comment_update(run, repo, n, st, new_head, plan.main_tip, carried, run_url)
    return plan


def _post_update_head(run: Runner, repo: str, n: int, st: EntryState) -> str | None:
    try:
        pr = json.loads(_run(run, _rest_path(repo, f"pulls/{n}")))
        sha = pr.get("head", {}).get("sha")
        return str(sha) if sha is not None else None
    except Exception as exc:
        st.errors.append(f"post-update head read: {snap.error_text(exc)}")
        return None


def _arm_auto_merge(run: Runner, repo: str, n: int, st: EntryState, token: str | None) -> None:
    """UR-23's merge style (merge), via the GraphQL mutation -- the token's second allowed
    call, riding the write credential's per-call auth override. A failure is reported, never
    silent: an un-armed PR sits behind awaiting a coordinator roll it may not get."""
    try:
        pr_id = _pr_id(run, repo, n)
        if not pr_id:
            st.errors.append("arm auto-merge: the PR's GraphQL id is unread")
            return
        run(
            [
                "gh",
                "api",
                "graphql",
                *_auth(token),
                "-f",
                'query=mutation { enablePullRequestAutoMerge(input: { pullRequestId: "'
                + pr_id
                + '", mergeMethod: MERGE }) { pullRequest { number } } }',
            ],
            "",
        )
    except Exception as exc:
        st.errors.append(f"arm auto-merge: {snap.error_text(exc)}")


def _disarm_auto_merge(run: Runner, repo: str, n: int, st: EntryState, token: str | None) -> None:
    try:
        pr_id = _pr_id(run, repo, n)
        if not pr_id:
            st.errors.append("disarm auto-merge: the PR's GraphQL id is unread")
            return
        run(
            [
                "gh",
                "api",
                "graphql",
                *_auth(token),
                "-f",
                'query=mutation { disablePullRequestAutoMerge(input: { pullRequestId: "'
                + pr_id
                + '" }) { pullRequest { number } } }',
            ],
            "",
        )
    except Exception as exc:
        st.errors.append(f"disarm auto-merge: {snap.error_text(exc)}")


def _pr_id(run: Runner, repo: str, n: int) -> str:
    owner, _, name = repo.partition("/")
    answer = json.loads(
        _run(
            run,
            'graphql -f query=query{repository(owner:"'
            + owner
            + '",name:"'
            + name
            + '"){pullRequest(number:'
            + str(n)
            + "){id}}}",
        )
    )
    return str(answer.get("data", {}).get("repository", {}).get("pullRequest", {}).get("id", ""))


def _carry_check(
    run: Runner, repo: str, st: EntryState, new_head: str | None, main_tip: str
) -> bool | None:
    """Step 6's re-check: the listed sha's own diff against the new head's, over the PR's
    own files -- the hash comparison first, and when the hashes differ, ruling 278's
    subset rule (an update merge of main can carry the diff the hash cannot). A carry
    holds only when both revs read and the decision says yes; None (a failed read, or a
    subset read that could not decide) is not a carry. Both revs hash against ``main``'s
    tip (the _hash_own per-rev merge-base semantics: the root is the same for every rev
    in one fire, each rev's merge-base with it differs)."""
    if new_head is None:
        return None
    files = _own_diff_files(run, repo, st.entry.number, st.errors)
    if files is None:
        return None
    listed = _diff_at(run, repo, st.entry.number, st.entry.sha, main_tip, files, st.errors)
    head = _diff_at(run, repo, st.entry.number, new_head, main_tip, files, st.errors)
    if listed is None or head is None:
        return None
    if listed.hash == head.hash:
        return True
    return _subset_carry(
        run, repo, st.entry.number, listed, head, main_tip, files, st.errors
    )


def _comment_update(
    run: Runner,
    repo: str,
    n: int,
    st: EntryState,
    new_head: str | None,
    main_tip: str | None,
    carried: bool | None,
    run_url: str,
) -> None:
    """Step 7's one comment: old and new head, ``main``'s tip, the two own-diff hashes and
    the run link. Ruling 272 item 6 makes this comment the own-diff comparison UR-106's
    condition 1 asks the coordinator to quote. Both revs hash against ``main``'s tip (the
    _hash_own per-rev semantics); the carry line names the verdict the two hashes or the
    ruling-278 subset rule reached."""
    try:
        files = _own_diff_files(run, repo, n, st.errors)
        listed = _hash_at(run, repo, n, st.entry.sha, main_tip or "", files or [], st.errors)
        head = _hash_at(
            run, repo, n, new_head or st.head or "", main_tip or "", files or [], st.errors
        )
    except Exception as exc:  # a failed hash read degrades the comment, not the update
        st.errors.append(f"comment hashes: {snap.error_text(exc)}")
        listed = head = None
    body = (
        f"Queue update (ruling 272): `{st.entry.sha[:9] if st.entry.sha else '?'} -> "
        f"{new_head[:9] if new_head else '?'}"
        f"`; main tip `{main_tip[:9] if main_tip else '?'}`"
        f"; own-diff hash `{listed[:12] if listed else 'unread'} -> "
        f"{head[:12] if head else 'unread'}`"
        f" (carry: {'yes' if carried else 'no' if carried is False else 'unread'})"
        + (f"; run: {run_url}" if run_url else "")
        + "."
    )
    try:
        run(
            [
                "gh",
                "api",
                "-X",
                "POST",
                _rest_path(repo, f"issues/{n}/comments"),
                "-F",
                f"body={body}",
            ],
            "",
        )
    except Exception as exc:
        st.errors.append(f"comment: {snap.error_text(exc)}")


def fire(run: Runner, repo: str, issue: int, token: str | None, run_url: str = "") -> Plan:
    """One fire: read, decide, act -- and fall through once on a 409.

    Steps 2-4 decide which entry acts; steps 5-7 act on it. A conflicting update
    (``act`` set ``action = "conflict-fallthrough"``) re-runs the skip ladder with the
    conflicted entry removed and acts on the NEXT eligible entry in the same fire --
    ruling 272 step 5's "the next entry acts in the same fire" -- but at most one
    successful update happens per fire, so a second conflict ends the fire as a no-op.
    """
    plan = Plan()
    plan.queue_entries, plan.main_tip, plan.main_ci_conclusion, plan.read_errors = read_state(
        run, repo, issue
    )
    decide(run, repo, plan, issue)
    act(run, repo, plan, token, run_url)
    if plan.action != "conflict-fallthrough":
        return plan
    conflicted = plan.acted_entry
    plan = Plan(
        main_tip=plan.main_tip,
        main_ci_conclusion=plan.main_ci_conclusion,
        # the conflicted entry leaves the QUEUE too (not just entries): decide()'s no-entry-
        # acted fallback (`if plan.queue_entries: no-op`) and the red-main filter both read
        # this list, so a stale row here would let the re-decide re-pick the entry that
        # just 409ed and burn this fire's single update on a retry.
        queue_entries=[e for e in plan.queue_entries if e.number != conflicted],
        read_errors=plan.read_errors,
        entries=[s for s in plan.entries if s.entry.number != conflicted],
    )
    decide(run, repo, plan, issue)  # the re-decide reads afresh, over the surviving entries
    if plan.action == "update":
        act(run, repo, plan, token, run_url)
        if plan.action == "conflict-fallthrough":  # two conflicts: stop, the next fire retries
            plan.action = "no-op"
            plan.action_note = "a second entry conflicted too: nothing updated this fire"
            return plan
        return plan
    plan.action = "no-op"
    if not plan.action_note:
        plan.action_note = f"the next entry after #{conflicted}'s conflict gave no update"
    return plan


def render_summary(plan: Plan) -> str:
    """The job summary, capped at ``SUMMARY_LINES``: what the fire saw and did, even when
    it did nothing (step 7's every-fire duty)."""
    lines = [
        "## Queue update (ruling 272)",
        "",
        f"- main tip: `{plan.main_tip[:12] if plan.main_tip else 'unread'}`",
        f"- main CI: {plan.main_ci_conclusion if plan.main_ci_conclusion else 'none completed (in flight)'}",
        f"- queue: {' '.join(e.render() for e in plan.queue_entries) if plan.queue_entries else '(empty)'}",
    ]
    if plan.read_errors:
        lines.append(f"- read errors: {'; '.join(plan.read_errors)}")
    lines.append("")
    lines.append("| entry | state | behind | gate | head | notes |")
    lines.append("|---|---|---|---|---|---|")
    for st in plan.entries:
        notes = "; ".join([*st.errors])
        lines.append(
            f"| #{st.entry.number}@{st.entry.sha[:9]}" + f"{' (urgent)' if st.entry.urgent else ''}"
            f" | {st.state or 'unread'} | {st.behind if st.behind is not None else 'unread'}"
            f" | {st.gate_failed if st.gate_failed is not None else 'unread'}"
            f" | {st.head[:9] if st.head else 'unread'} | {notes or '-'} |"
        )
    lines.append("")
    lines.append(f"**action: {plan.action}** {plan.action_note}".rstrip())
    out = "\n".join(lines)
    if out.count("\n") > SUMMARY_LINES:
        out = "\n".join(out.splitlines()[:SUMMARY_LINES]) + "\n… (summary capped)\n"
    return out


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="scripts/uplevel/queue_update.py",
        description="update the next queued PR when main moves (ruling 272)",
    )
    ap.add_argument("--repo", default=DEFAULT_REPO, type=snap._repo_arg)
    ap.add_argument("--issue", type=int, default=OWNER_ISSUE, help="the ruling/status issue")
    ap.add_argument("--dry-run", action="store_true", help="print the plan; write nothing")
    return ap


def real_run(cmd: Sequence[str], stdin: str = "") -> str:
    """The real runner: ``gh api``/``git`` with stdout returned, CommandError on failure;
    ``stdin`` is piped in -- the update-branch PUT body rides it.

    On a non-zero exit the stdout rides the raise (``_gh_rest`` reads the ``--include``
    status line off it): ``gh api`` exits 1 on every HTTP >= 400 while the status line is
    stdout, so a discard-the-stdout raise would read every conflict as status 0 (N10).
    A timeout raises CommandError-shaped too, argv truncated to ``cmd[:3]``: a raw
    ``TimeoutExpired``'s str() carries the FULL argv -- including
    ``-H "Authorization: token <QUEUE_UPDATE_TOKEN>"`` on the write calls -- and
    ``snap.error_text`` renders a non-CommandError exception verbatim, which would put the
    write credential into the job summary on a public repo (r5 B2)."""
    try:
        proc = subprocess.run(
            list(cmd), input=stdin, capture_output=True, text=True, check=False, timeout=120
        )
    except subprocess.TimeoutExpired as exc:
        raise _CarryingError(f"{' '.join(cmd[:3])} timed out after {exc.timeout}s") from None
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout).strip().splitlines()
        err = _CarryingError(
            f"{' '.join(cmd[:3])} exited {proc.returncode}: {tail[-1] if tail else 'no output'}"
        )
        err.stdout = proc.stdout  # the --include status line survives the raise (N10)
        raise err
    return proc.stdout


def main(argv: Sequence[str] | None = None, run: Runner | None = None) -> int:
    a = parser().parse_args(argv)
    token = os.environ.get("QUEUE_UPDATE_TOKEN") if not a.dry_run else None
    try:
        plan = fire(run or real_run, a.repo, a.issue, token, os.environ.get("GITHUB_RUN_URL", ""))
    except Exception as exc:
        print(f"ERROR fire: {snap.error_text(exc)}", file=sys.stderr)
        return 1
    summary = render_summary(plan)
    print(summary)
    if a.dry_run:
        print("\n(dry run: nothing written)")
    elif os.environ.get("GITHUB_STEP_SUMMARY"):
        try:
            # GITHUB_STEP_SUMMARY is runner-owned (GitHub sets it per step), not user input;
            # the annotation rides the line semgrep matches (the `with`), as in analyze-flaky-tests.py.
            # nosemgrep: path-traversal-open - runner-owned path, not user input
            with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as fh:
                fh.write(summary + "\n")
        except OSError as exc:
            print(f"ERROR summary write: {exc}", file=sys.stderr)
    return 0 if plan.action in ("none", "no-op", "update") or not plan.read_errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
