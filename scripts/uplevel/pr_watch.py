#!/usr/bin/env python3
"""Watch the PRs this agent cares about and print one line when something changes (ruling 193).

The problem this solves: an agent polling GitHub by hand burns a turn per check and still misses
the moment. This watcher is armed as a background command and exits the instant a watched PR
moves, so the agent wakes on news instead of on a timer.

Everything it reads arrives through one seam: a ``runner(query, variables) -> dict`` callable that
stands for the single batched GraphQL request a poll makes (``gh_runner`` in ``main``). The clock
and sleeper are injected for the same reason -- ``scripts/test_pr_watch.py`` drives every path
below with no monkeypatching and no network, and a read nobody scripted raises there rather than
reaching the API from a test.

Three properties are deliberate and load-bearing:

* **One GraphQL query per poll, never the ``search`` API.** Search is limited to 30 requests per
  minute *shared across every agent on the owner's token*; a node query is not. Ruling 193 names
  this explicitly and the test greps the recorded query text for ``search(``.
* **It prints no comment bodies.** Watched threads carry review text and incidental secrets; the
  agent that wakes reads the thread it was told about, with the authority to quote it. A watcher
  that echoed bodies would leak them into whatever log backs the background task.
* **Silence is never success.** A bounded lifetime ends with a "no change" line and repeated API
  failures end with an error line and a non-zero exit, so a dead watcher cannot impersonate a
  healthy one sitting in the background.

Usage (what an agent arms; see docs/uplevel/roles/lane.md "The tick"):

    uv run python scripts/uplevel/pr_watch.py --pr 7168 --pr 7175 --lifetime 3600 &
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta

DEFAULT_REPO = "mikesvoboda/nemotron-v3-home-security-intelligence"
RULING_ISSUE = 6854
BINDING_MARKER = "BINDING NOW"


def query_variables(prs: Sequence[int], repo: str, ruling_issue: int) -> dict:
    """The variables for one poll. Every watched PR gets its own ``$p<number>`` argument."""
    owner, name = repo.split("/", 1)  # a repo string without the owner is a caller error
    variables: dict = {"owner": owner, "name": name, "ri": ruling_issue}
    for number in prs:
        variables[f"p{number}"] = number
    return variables


def query_text(prs: Sequence[int], repo: str, ruling_issue: int) -> str:
    """The one GraphQL query a poll runs: one aliased node per watched PR, plus #6854.

    One ``repository`` root, aliased children. A PR that is inaccessible comes back null under
    its own alias, so the parse below reads each alias independently and a deleted PR cannot
    shift the others. The body of a comment is fetched -- and only used to spot the
    ``BINDING NOW`` marker; see the module docstring for why it is never printed.
    """
    declarations = ["$owner: String!", "$name: String!", "$ri: Int!"]
    declarations += [f"$p{number}: Int!" for number in prs]
    fields = "\n".join(
        [
            "    number",
            "    headRefOid",
            "    state",
            "    isDraft",
            "    labels(first: 20) { nodes { name } }",
            # `contexts`, not `nodes`: measured against the live schema -- StatusCheckRollup is an
            # object exposing a `contexts` connection (introspection: fields = commit, contexts,
            # id, state). Asking for `nodes` there is rejected outright.
            # `last:` here too: check runs append, so a first:-100 window would drop the NEWEST
            # runs once a head exceeds 100 checks -- and `CI Gate (Required Checks)` is created
            # after its `needs`, i.e. at the new end. Measured 53 contexts for #7175 today.
            "    statusCheckRollup {",
            "      contexts(last: 100) {",
            "        nodes {",
            "          ... on CheckRun { name conclusion status }",
            "          ... on StatusContext { context state }",
            "        }",
            "      }",
            "    }",
            # `last:`, never `first:`: these connections are oldest-first and the watcher's whole
            # job is the NEW end. Measured at write time: #6854 has 646 comments, so
            # `first: 100` returned the oldest hundred with hasNextPage true and zero BINDING NOW
            # entries in them, while `last: 100` held 30. A `first:` watcher would run green
            # forever and never report a ruling.
            "    reviews(last: 100) { nodes { id author { login } } }",
            "    comments(last: 100) { nodes { id author { login } body } }",
        ]
    )
    lines = [f"query({', '.join(declarations)}) {{", "  repository(owner: $owner, name: $name) {"]
    for number in prs:
        lines.append(f"    p{number}: pullRequest(number: $p{number}) {{")
        lines.append(fields)
        lines.append("    }")
    lines.append("    issue(number: $ri) {")
    lines.append("      number")
    # `last:`, and this is the one that mattered: #6854 carries 646 comments (measured), so
    # `first: 100` returned the oldest hundred -- zero BINDING NOW entries, hasNextPage true --
    # while `last: 100` held 30. A first:-100 watcher would run green forever and never report a
    # ruling. A comment newer than the window cannot exist: anything new is in the newest 100.
    lines.append("      comments(last: 100) { nodes { id author { login } body } }")
    lines.append("    }")
    lines.append("  }")
    lines.append("}")
    return "\n".join(lines)


def snapshot(data: dict, prs: Sequence[int]) -> dict:
    """Reduce one GraphQL response to the comparable state dict a poll diffs against.

    A null PR node (inaccessible or deleted) is stored as ``None`` and stays ``None``, which
    yields no lines rather than a spurious "closed".
    """
    root = data.get("repository") or {}
    state: dict = {"prs": {}, "ruling": None}
    for number in prs:
        node = root.get(f"p{number}")
        state["prs"][number] = None if node is None else _pr_fields(node)
    issue = root.get("issue")
    if issue is not None:
        comments = _comments(issue.get("comments"))
        state["ruling"] = {
            "binding": sorted(
                (cid, login) for cid, login, body in comments if BINDING_MARKER in (body or "")
            )
        }
    return state


def _pr_fields(node: dict) -> dict:
    return {
        "head": node.get("headRefOid"),
        "state": node.get("state"),
        "isDraft": node.get("isDraft"),
        "labels": sorted(n.get("name") for n in (node.get("labels") or {}).get("nodes") or []),
        "checks": _checks(node.get("statusCheckRollup")),
        "reviews": sorted(
            (r.get("id"), (r.get("author") or {}).get("login"))
            for r in (node.get("reviews") or {}).get("nodes") or []
        ),
        "comments": sorted((c[0], c[1]) for c in _comments(node.get("comments"))),
    }


def _comments(wrapper) -> list[tuple[str, str | None, str | None]]:
    nodes = (wrapper or {}).get("nodes") or []
    return [
        (n.get("id"), (n.get("author") or {}).get("login"), n.get("body"))
        for n in nodes
        if n.get("id") is not None
    ]


def _checks(rollup) -> dict[str, str]:
    """{check name: conclusion} for checks that HAVE a conclusion.

    ``rollup`` is a StatusCheckRollup object; its checks live under ``contexts.nodes`` (see the
    query comment). A check still in flight has no conclusion, and reporting one would report a
    verdict that has not been reached -- the test pins that an ``IN_PROGRESS`` rollup yields no
    line. ``StatusContext`` nodes carry ``context``/``state`` instead of ``name``/``conclusion``,
    so both spellings are read.
    """
    nodes = ((rollup or {}).get("contexts") or {}).get("nodes") or []
    out: dict[str, str] = {}
    for node in nodes:
        name = node.get("name") or node.get("context")
        conclusion = node.get("conclusion") or node.get("state")
        if name and conclusion and conclusion != "PENDING":
            out[name] = conclusion
    return out


def diff_lines(prs: Sequence[int], ruling_issue: int, before: dict, after: dict) -> list[str]:
    """The change lines: one per change class, each naming the PR and what moved."""
    lines: list[str] = []
    for number in prs:
        old, new = before["prs"].get(number), after["prs"].get(number)
        if old is None or new is None:
            continue
        prefix = f"#{number} "
        if new["state"] != old["state"]:
            lines.append(f"{prefix}{'merged' if new['state'] == 'MERGED' else 'closed'}")
            continue  # a closed PR's other fields are noise; the merge/close IS the news
        if new["head"] != old["head"]:
            lines.append(f"{prefix}new head {old['head'][:7]} -> {new['head'][:7]}")
        for check_name, conclusion in sorted(new["checks"].items()):
            if old["checks"].get(check_name) != conclusion:
                was = old["checks"].get(check_name, "no conclusion")
                lines.append(f"{prefix}check {check_name}: {was} -> {conclusion}")
        if new["reviews"] != old["reviews"]:
            who = _new_actor(new["reviews"], old["reviews"])
            lines.append(f"{prefix}new review{_from(who)}")
        if new["comments"] != old["comments"]:
            who = _new_actor(new["comments"], old["comments"])
            lines.append(f"{prefix}new comment{_from(who)}")  # author only; never the body
        if new["labels"] != old["labels"]:
            added = sorted(set(new["labels"]) - set(old["labels"]))
            removed = sorted(set(old["labels"]) - set(new["labels"]))
            parts = [f"+{label}" for label in added] + [f"-{label}" for label in removed]
            lines.append(f"{prefix}label {' '.join(parts)}")
    old_ruling, new_ruling = before.get("ruling"), after.get("ruling")
    if old_ruling and new_ruling:
        known = {cid for cid, _login in old_ruling["binding"]}
        for cid, login in new_ruling["binding"]:
            if cid not in known:
                lines.append(f"#{ruling_issue} new {BINDING_MARKER} (comment {cid}{_from(login)})")
    return lines


def _from(login: str | None) -> str:
    return "" if not login else f" from {login}"


def _new_actor(after: list, before: list) -> str | None:
    """The author of the first item in ``after`` that isn't in ``before``, if identifiable."""
    seen = {item[0] for item in before}
    for item in after:
        if item[0] not in seen:
            return item[1]
    return None


def check(
    runner: Callable[[str, dict], dict],
    state: dict,
    now: datetime,
    *,
    repo: str = DEFAULT_REPO,
    prs: Sequence[int] = (),
    ruling_issue: int = RULING_ISSUE,
) -> list[str]:
    """One poll. Seeds ``state`` on the first call (reporting nothing); then reports changes.

    The first poll is deliberately silent: an agent arms this watcher mid-tick, and the heads,
    check verdicts and comments that already existed are not news -- reporting them would make
    every arm look like an event.
    """
    response = runner(query_text(prs, repo, ruling_issue), query_variables(prs, repo, ruling_issue))
    after = snapshot(response.get("data") or {}, prs)
    if not state:
        state.update(after)
        return []
    lines = diff_lines(prs, ruling_issue, state, after)
    state.clear()
    state.update(after)
    return lines


def watch(
    runner: Callable[[str, dict], dict],
    state: dict,
    clock: Callable[[], datetime],
    sleep: Callable[[float], None],
    *,
    repo: str = DEFAULT_REPO,
    prs: Sequence[int] = (),
    ruling_issue: int = RULING_ISSUE,
    interval: float = 60.0,
    lifetime: float = 3600.0,
    max_errors: int = 3,
) -> tuple[int, list[str]]:
    """Poll until something changes, the lifetime ends, or the API keeps failing.

    Returns ``(exit_code, lines)``; ``main`` prints the lines and exits with the code. One poll
    per ``interval`` for at most ``lifetime`` seconds -- the bound exists so a backgrounded
    watcher always terminates with a line the agent can read, rather than running forever unseen.
    """
    start = clock()
    errors = 0
    while True:
        if clock() - start >= timedelta(seconds=lifetime):
            return 0, [f"no change in {int(lifetime)}s across {len(prs)} watched PR(s)"]
        try:
            lines = check(runner, state, clock(), repo=repo, prs=prs, ruling_issue=ruling_issue)
        except Exception as exc:
            # Deliberately broad: any transient API/parse failure is retried, and only the
            # max_errors streak makes it fatal. A narrow `except` here would let an unexpected
            # error type kill the background watch on tick one -- which reads as "no change".
            errors += 1
            if errors >= max_errors:
                return 2, [f"error: {errors} consecutive poll failures; last: {exc}"]
        else:
            errors = 0
            if lines:
                return 0, lines
        sleep(interval)


def gh_args(query: str, variables: dict) -> list[str]:
    """The argv for one poll. Split out so the flag spelling is testable without a subprocess.

    ``gh api`` has no ``--var``: GraphQL variables are ``-f`` for strings and ``-F`` for typed
    values, and an Int variable passed with ``-f`` is rejected as a String. The first live call is
    what found that, so it is pinned by a test rather than by memory.
    """
    args = ["gh", "api", "graphql", "-f", f"query={query}"]
    for key, value in variables.items():
        flag = "-F" if isinstance(value, int) and not isinstance(value, bool) else "-f"
        args += [flag, f"{key}={value}"]
    return args


def gh_runner(query: str, variables: dict) -> dict:
    """The production seam: one ``gh api graphql`` call, parsed -- or raised, never swallowed."""
    proc = subprocess.run(gh_args(query, variables), capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip()[:400])
    payload = json.loads(proc.stdout)
    if payload.get("errors"):
        raise RuntimeError(str(payload["errors"])[:400])
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument(
        "--pr",
        action="append",
        type=int,
        dest="prs",
        default=[],
        help="a PR to watch; repeat for each one",
    )
    parser.add_argument("--ruling-issue", type=int, default=RULING_ISSUE)
    parser.add_argument("--interval", type=float, default=60.0, help="seconds between polls")
    parser.add_argument("--lifetime", type=float, default=3600.0, help="seconds before quitting")
    parser.add_argument("--max-errors", type=int, default=3)
    args = parser.parse_args(argv)
    if not args.prs:
        parser.error("no --pr given: name the PRs to watch")

    rc, lines = watch(
        gh_runner,
        {},
        lambda: datetime.now(UTC),
        time.sleep,
        repo=args.repo,
        prs=list(args.prs),
        ruling_issue=args.ruling_issue,
        interval=args.interval,
        lifetime=args.lifetime,
        max_errors=args.max_errors,
    )
    for line in lines:
        print(line)  # this line on stdout is the CLI's entire contract with the agent
    return rc


if __name__ == "__main__":
    sys.exit(main())
