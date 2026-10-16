#!/usr/bin/env python3
"""Watch the PRs this agent cares about, and exit with one line per change it saw (ruling 193).

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
# The most nodes a discovery connection asks for. GitHub caps any connection page at 100, so a
# match beyond this is TRUNCATION, not a quiet tick -- see _check_windows.
DISCOVERY_WINDOW = 100
# The most comments/reviews a watched PR's event connections ask for. Same cap, but here the number
# is also what `_event_lines` compares a vanished id against: a window that came back SHORTER than
# this held every item that exists, so a gone id was really deleted; a FULL window cannot say, and
# the line degrades to "missing" (see _event_lines). The query interpolates this so the ask and the
# comparison are one number and cannot drift apart -- the same reason test_window_size_is_bounded_by
# _a_named_constant pins DISCOVERY_WINDOW.
EVENT_WINDOW = 100


def label_groups(lane: str, cell: str, review_labels: Sequence[str]) -> list[list[str]]:
    """One single-label group per label ruling 193 names: my lane, my cell, then each review label.

    Ruling 193 names three kinds -- "its lane, cell and `review:<lane>` labels" -- and each gets its
    own aliased connection, never a merged one, for a reason measured against the live API: a
    connection's ``labels:`` argument is **OR**, not AND. Two labels no PR can carry together
    (``lane:ops``, 82 PRs, and ``lane:docs``, 56) came back as one query of 138 with an empty
    intersection -- AND would have returned 0. So putting ``lane:ops`` and ``cell:a`` in one
    connection cannot narrow anything (the union already includes every ops PR, of either cell), and
    because ``discovered`` names the labels whose connection matched, a merged group would print a
    label the PR does not carry. One connection per label keeps every word of the watch line true.
    """
    given = [f"lane:{lane}" if lane else "", f"cell:{cell}" if cell else "", *review_labels]
    return [[label] for label in given if label]


def query_variables(
    prs: Sequence[int], repo: str, ruling_issue: int, groups: Sequence[Sequence[str]] = ()
) -> dict:
    """The variables for one poll: every watched PR as ``$p<number>``, every label as ``$a<i>_<j>``.

    Labels ride one variable each rather than a list: ``gh api graphql -F 'a0=["lane:ops"]'``
    returned ``{"nodes": []}`` with NO error against the live API -- a silently empty watch -- while
    a per-element ``String!`` on ``-f`` matched correctly.
    """
    owner, name = repo.split("/", 1)  # a repo string without the owner is a caller error
    variables: dict = {"owner": owner, "name": name, "ri": ruling_issue}
    for number in prs:
        variables[f"p{number}"] = number
    for i, group in enumerate(groups):
        for j, label in enumerate(group):
            variables[f"a{i}_{j}"] = label
    return variables


def query_text(
    prs: Sequence[int], repo: str, ruling_issue: int, groups: Sequence[Sequence[str]] = ()
) -> str:
    """The one GraphQL query a poll runs: discovery connections, one aliased node per watched PR,
    plus #6854.

    One ``repository`` root, aliased children. A PR that is inaccessible comes back null under
    its own alias, so the parse below reads each alias independently and a deleted PR cannot
    shift the others. The body of a comment is fetched -- and only used to spot the
    ``BINDING NOW`` marker; see the module docstring for why it is never printed.
    """
    declarations = ["$owner: String!", "$name: String!", "$ri: Int!"]
    declarations += [f"$p{number}: Int!" for number in prs]
    declarations += [f"$a{i}_{j}: String!" for i, g in enumerate(groups) for j in range(len(g))]
    fields = "\n".join(
        [
            "    number",
            "    headRefOid",
            "    state",
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
            f"    reviews(last: {EVENT_WINDOW}) {{ nodes {{ id author {{ login }} }} }}",
            f"    comments(last: {EVENT_WINDOW}) {{ nodes {{ id author {{ login }} body }} }}",
        ]
    )
    lines = [f"query({', '.join(declarations)}) {{", "  repository(owner: $owner, name: $name) {"]
    for i, group in enumerate(groups):
        args = ", ".join(f"$a{i}_{j}" for j in range(len(group)))
        lines.append(f"    a{i}: pullRequests(labels: [{args}], states: [OPEN],")
        # `states: [OPEN]`, and `UPDATED_AT` with an explicit `orderBy`: measured without the state
        # filter, `labels: ["lane:ops"]` matched 82 PRs against 6 open ones (measured 2026-10-15 --
        # the count drifts, the ratio does not), most of them long merged, and each of the matches
        # would become a field alias in this same query. `UPDATED_DESC` is rejected outright: this
        # connection orders by IssueOrderField, whose values are CREATED_AT/UPDATED_AT/COMMENTS.
        # `totalCount` because a full window and an empty one are otherwise indistinguishable.
        lines.append(
            f"      first: {DISCOVERY_WINDOW}, orderBy: {{field: UPDATED_AT, direction: DESC}}) {{"
        )
        lines.append("        nodes { number }")
        lines.append("        totalCount")
        lines.append("      }")
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


def discovered(data: dict, groups: Sequence[Sequence[str]]) -> dict[int, list[str]]:
    """{PR number: every label whose connection matched it} from this response's discovery.

    EVERY, not the first: groups are one label each (see ``label_groups``), and a PR of my cell
    sits in two connections -- the lane's and the cell's -- so the watch line and the state entry
    name both. Dropping the second would not misreport membership (the PR is watched either way),
    but the line is the agent's only record of WHY a PR joined, and half a reason is a claim about
    a label match that the other connection proved did not happen alone.
    """
    root = data.get("repository") or {}
    found: dict[int, list[str]] = {}
    for i, group in enumerate(groups):
        for node in _connection(root.get(f"a{i}")) or []:
            number = node.get("number")
            if number is None:
                continue
            reasons = found.setdefault(number, [])
            reasons.extend(label for label in group if label not in reasons)
    return found


def _connection(wrapper: dict | None) -> list[dict] | None:
    return (wrapper or {}).get("nodes") if wrapper else None


def _check_windows(data: dict, groups: Sequence[Sequence[str]]) -> None:
    """Refuse to watch a TRUNCATED discovery window.

    A connection that returns exactly ``DISCOVERY_WINDOW`` nodes while ``totalCount`` says there
    are more has hidden PRs -- and a watcher that quietly skips them reads as a calm tick, which is
    the failure this module exists to avoid. ``totalCount`` is a real field (introspected:
    PullRequestConnection = edges/nodes/pageInfo/totalCount), so the comparison is with the server's
    own count rather than a heuristic. Raising routes through ``watch``'s error path: an error line
    and a non-zero exit.
    """
    root = data.get("repository") or {}
    for i in range(len(groups)):
        wrapper = root.get(f"a{i}")
        if not wrapper:
            continue
        nodes = wrapper.get("nodes") or []
        total = wrapper.get("totalCount")
        if len(nodes) >= DISCOVERY_WINDOW and (total is None or total > DISCOVERY_WINDOW):
            msg = (
                f"discovery window full: {len(nodes)} of {total} PRs matched -- "
                f"{DISCOVERY_WINDOW} is the most one poll can watch"
            )
            raise RuntimeError(msg)


def _check_explicit(data: dict, prs: Sequence[int]) -> None:
    """Refuse to watch a poll that answers an explicitly asked-for PR with null.

    ``snapshot`` stores ``None`` for an absent/null ``p<number>`` and ``diff_lines`` then skips any
    pair where either side is unreadable, so a PR that is answered null for one poll and comes back
    changed on the next reports NOTHING: the head change that straddled the null window is gone, and
    it is gone silently for good because ``before`` on the following poll is the null snapshot.
    Discovered PRs have the UNREAD carry-forward for that shape; an explicit ``--pr`` has nothing,
    and it is the one channel that cannot relearn its membership -- label discovery will never hand
    back a number the agent already typed. Same reasoning as ``_check_ruling``: raise, and let
    ``watch``'s error path decide, so a transient null costs one error credit (``state`` still holds
    the last GOOD snapshot, so the straddling change prints on the next successful poll) and a
    prolonged one exits rc 2 with an error line rather than reading as a calm tick.
    """
    root = data.get("repository") or {}
    missing = [number for number in prs if root.get(f"p{number}") is None]
    if missing:
        numbers = ", ".join(f"#{number}" for number in missing)
        msg = (
            f"explicitly watched {numbers} came back null or absent -- its changes during the null"
            " window are unrecoverable, and a watcher that skips them reads as calm while they pass"
        )
        raise RuntimeError(msg)


def _check_read_gone_null(before: dict, after: dict) -> None:
    """A PR the watcher has already READ, answered null this poll, is a broken watch -- raise.

    ``diff_lines`` skips any pair whose either side is unreadable, so a head/check/state change that
    straddles a null window never prints -- and never prints twice, because the next poll's ``before``
    IS the null snapshot. The loss is silent and permanent, exactly the "calm tick over a gap" failure
    this module exists to prevent. It is ``_check_explicit``'s failure reached by the OTHER channel: a
    DISCOVERED PR the watcher read once -- so it is no longer ``UNREAD`` and the UNREAD carry-forward
    no longer applies -- that GitHub then answers null. A still-``UNREAD`` PR answered null is a
    different case the carry-forward owns (its fields were never lost, only never yet read), so this
    guard fires only on an entry that was ``_read`` and turns to ``None``, and routes through
    ``watch``'s error path: a transient null costs one error credit and leaves ``state`` on the last
    GOOD snapshot (the straddling change prints on the next successful poll), a prolonged one exits
    rc 2 with an error line rather than reading as a quiet watch.
    """
    lost = [n for n in after["prs"] if after["prs"][n] is None and _read(before["prs"].get(n))]
    if lost:
        numbers = ", ".join(f"#{n}" for n in sorted(lost))
        raise RuntimeError(
            f"watched {numbers} was read on an earlier poll and came back null -- a change during"
            " the null window would be lost silently and for good, so the watcher exits rather than"
            " report a calm tick it cannot see through"
        )


def _check_ruling(data: dict, ruling_issue: int) -> None:
    """Refuse to watch a poll that cannot see the ruling issue.

    ``snapshot`` stores ``state["ruling"] = None`` when the ``issue`` node is absent or null, and
    ``diff_lines`` then compares only ``if old_ruling and new_ruling`` -- so a seed poll that
    cannot see #6854 never compares it again: a ``BINDING NOW`` can arrive, be fetched, and
    report nothing, for the watcher's whole lifetime, with zero errors. The discovery path has
    ``_check_windows`` for exactly this shape of silence; the ruling channel had none. Raising
    here sends it through ``watch``'s error path -- an error line and rc 2 -- instead of a calm
    forever. The null can be a real event (issue deleted or made inaccessible), and then dying
    loudly is still the honest answer: a lane that cannot see its rulings is not a watching lane.
    """
    root = data.get("repository") or {}
    if root.get("issue") is None:
        msg = (
            f"ruling issue #{ruling_issue} came back null or absent -- the BINDING NOW channel"
            " is unreadable and a watcher that ignores it reads as calm while rulings pass"
        )
        raise RuntimeError(msg)


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
        # binding keeps the window's chronological order (see _pr_fields), not a cid sort. The backfill
        # decision is made on the RAW window, not on this filtered list: `window_ids` is every comment
        # id in the window in order, so a real arrival is anchored against ~100 shared ids no matter how
        # many of them happen to bind (a filtered list can have no anchor at all -- zero shared BINDING
        # rows -- and then position proves nothing). window_full is the RAW length too: truncation is a
        # property of the connection, not of how many of its rows bind.
        state["ruling"] = {
            "binding": [(cid, login) for cid, login, body in comments if _binding(body)],
            "window_ids": [cid for cid, _login, _body in comments],
            "window_full": len(comments) >= EVENT_WINDOW,
        }
    return state


def _binding(body: str | None) -> bool:
    """True when ``body`` is a UR-40 owner record that binds at once.

    UR-40 is exact: an owner record binds when its FIRST LINE carries ``BINDING NOW``. Matching the
    marker anywhere in the body is wrong, and not hypothetically -- #6854 comment `6180424930` opens
    with ``URGENT PATH · coordinator stale again`` and mentions ``BINDING NOW`` on a later line (its
    status text counts "42 BINDING NOW rows in window"), so a substring match wakes the lane for a
    comment that only names the marker, not one that issues a record. The whole point of the watcher
    is to be trusted when it prints, so it prints only on the shape the rule names.
    """
    first = (body or "").lstrip().splitlines()
    return bool(first) and BINDING_MARKER in first[0]


def _pr_fields(node: dict) -> dict:
    return {
        "head": node.get("headRefOid"),
        "state": node.get("state"),
        "labels": sorted(n.get("name") for n in (node.get("labels") or {}).get("nodes") or []),
        "checks": _checks(node.get("statusCheckRollup")),
        # reviews/comments keep the CONNECTION's order, NOT a sort. `last: EVENT_WINDOW` returns them
        # oldest-first (measured on #6854: the 100 comments run strictly ascending by createdAt), and
        # `_event_lines` reads that position to tell a genuine arrival (above the window) from a
        # backfill (an old id re-entering below it when the newest is deleted). Lexical order is NOT
        # chronological -- sorting turns "C_101" ahead of "C_2" -- so sorting here would suppress real
        # appends and admit backfills. Order is stable because createdAt is unique and ascending.
        # Labels below stay sorted: a label set has no chronology and its order is not an event.
        "reviews": [
            (r.get("id"), (r.get("author") or {}).get("login"))
            for r in (node.get("reviews") or {}).get("nodes") or []
            if r.get("id") is not None
        ],
        "comments": [(c[0], c[1]) for c in _comments(node.get("comments"))],
    }


def _comments(wrapper: dict | None) -> list[tuple[str, str | None, str | None]]:
    nodes = (wrapper or {}).get("nodes") or []
    return [
        (n.get("id"), (n.get("author") or {}).get("login"), n.get("body"))
        for n in nodes
        if n.get("id") is not None
    ]


def _checks(rollup: dict | None) -> dict[str, str]:
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
    """The change lines: one per change class, each naming the PR and what moved.

    Only numbers with a READ state on both sides are compared -- a PR registered but not yet read
    (``UNREAD``) or read as null has nothing to diff, and reporting one would report a verdict read
    from nothing.
    """
    lines: list[str] = []
    for number in prs:
        old, new = before["prs"].get(number), after["prs"].get(number)
        if not _read(old) or not _read(new):
            continue
        prefix = f"#{number} "
        if new["state"] != old["state"]:
            lines.append(prefix + _state_line(new["state"]))
            continue  # a closed PR's other fields are noise; the merge/close IS the news
        if new["head"] != old["head"]:
            lines.append(f"{prefix}new head {old['head'][:7]} -> {new['head'][:7]}")
        for check_name, conclusion in sorted(new["checks"].items()):
            if old["checks"].get(check_name) != conclusion:
                was = old["checks"].get(check_name, "no conclusion")
                lines.append(f"{prefix}check {check_name}: {was} -> {conclusion}")
        if new["reviews"] != old["reviews"]:
            lines.extend(_event_lines(prefix, "review", new["reviews"], old["reviews"]))
        if new["comments"] != old["comments"]:
            lines.extend(_event_lines(prefix, "comment", new["comments"], old["comments"]))
        if new["labels"] != old["labels"]:
            added = sorted(set(new["labels"]) - set(old["labels"]))
            removed = sorted(set(old["labels"]) - set(new["labels"]))
            parts = [f"+{label}" for label in added] + [f"-{label}" for label in removed]
            lines.append(f"{prefix}label {' '.join(parts)}")
    old_ruling, new_ruling = before.get("ruling"), after.get("ruling")
    if old_ruling and new_ruling:
        # Same backfill class as the PR channels, and it costs more here: a false `new BINDING NOW`
        # wakes EVERY lane onto a ruling already carried out -- the opposite of UR-40's no-op rule.
        # The arrival test runs on the RAW window (`window_ids`), where ~100 shared ids anchor the
        # position; the binding list is then restricted to the records that both bind and sit at a
        # genuinely new position. Two shapes that must still pass: an arrival at the new end, and a
        # routine comment that was EDITED to bind -- same id, its position unchanged, but its body now
        # carries the marker, so it is a new ruling event and prints.
        # A BINDING record is "new" when it binds now and did not bind on the previous poll. Two
        # shapes qualify and BOTH must keep printing: a record that ARRIVED at the new end, and a
        # routine comment EDITED to carry the marker (same id, already in the window, position
        # unchanged -- a real ruling event). One shape must NOT print: a record GitHub BACKFILLED -- an
        # old BINDING that aged out and re-enters at the BOTTOM when the newest comment is deleted. It
        # binds now and did not bind last poll (it was not in the window at all), so the naive set
        # diff announces it, and that false line wakes every lane onto a ruling already carried out
        # (UR-40: a no-op, not a task). Anchor the position on the RAW window, where ~100 ids are
        # shared. The pre-position helper is bypassed here because the binding diff is not a plain
        # added-set: the edited-to-bind id is shared, not fresh, yet genuine -- so the gate is a
        # per-cid predicate, not "above the last shared id".
        new_ids = new_ruling.get("window_ids")
        old_ids = old_ruling.get("window_ids")
        old_bind = {cid for cid, _ in old_ruling["binding"]}
        if (
            new_ids is None or old_ids is None
        ):  # a snapshot shape without the window: prior behavior
            fresh = lambda cid: cid not in old_bind  # noqa: E731
        else:
            old_set = set(old_ids)
            idx = {cid: i for i, cid in enumerate(new_ids)}
            top_shared = max((idx[c] for c in old_set if c in idx), default=-1)
            # Re-entry is possible when EITHER window was truncated: an id that aged out of a FULL
            # previous window comes back once deletions shrink the window, and a window in hand that
            # reads SHORT does not prove the previous snapshot held every comment that exists.
            truncated = new_ruling.get("window_full", False) or old_ruling.get("window_full", False)

            def fresh(cid: object) -> bool:
                if cid in old_bind:
                    return False  # still binding -- not a new event either way
                if not truncated:
                    return True  # neither window truncated: every id that exists was in one poll
                if top_shared < 0:
                    return False  # no shared id: position is unprovable, so announce no arrival
                if cid in old_set:
                    return True  # edited-to-bind: was visible last poll, position rules don't apply
                return cid in idx and idx[cid] > top_shared  # a window-new id, at the new end

        for cid, login in new_ruling["binding"]:
            if fresh(cid):
                lines.append(f"#{ruling_issue} new {BINDING_MARKER} (comment {cid}{_from(login)})")
    return lines


# A PR discovered by label but not yet read: its number is known, its fields are not.
UNREAD = "unread"


def _read(entry: object) -> bool:
    return isinstance(entry, dict) and UNREAD not in entry


def _state_line(state: str) -> str:
    # Three outcomes, not two. `else "closed"` was the whole function, and it made any
    # non-MERGED change print "closed" -- so a REOPENED PR reported its opposite. A reopen is
    # not one of ruling 193's six change classes, but the state already being watched is what
    # the line exists to name, and naming it wrongly is worse than the class gap it exposes.
    return {"MERGED": "merged", "CLOSED": "closed", "OPEN": "reopened"}.get(state, state.lower())


def _watch_line(number: int, group: Sequence[str]) -> str:
    return f"#{number} watching (label {'+'.join(group)})"


def check(
    runner: Callable[[str, dict], dict],
    state: dict,
    *,
    repo: str = DEFAULT_REPO,
    prs: Sequence[int] = (),
    ruling_issue: int = RULING_ISSUE,
    label_groups: Sequence[Sequence[str]] = (),
) -> list[str]:
    """One poll. Seeds ``state`` on the first call (reporting nothing); then reports changes.

    The first poll is deliberately silent: an agent arms this watcher mid-tick, and the heads,
    check verdicts and comments that already existed are not news -- reporting them would make
    every arm look like an event.

    The watched set lives in ``state["watched"]`` and only GROWS: label discovery filters
    ``states: [OPEN]`` (an unfiltered lane query matched 82 PRs against 6 open ones, measured
    2026-10-15), so a merge takes a PR out of the
    discovery result, and a set that followed the query each poll would stop asking and never
    report the merge. A newly discovered PR is registered as ``UNREAD`` and named once -- then its
    fields are seeded by the next poll, so the first thing reported about it is a real change.
    """
    known = list(state.get("watched") or prs)
    # Seeded-ness, NOT emptiness. `not state.get("prs")` reads as the same question and is not:
    # a watcher armed by label alone over a lane with nothing routed to it has an EMPTY pr dict on
    # every poll, so it stayed "seeding" forever, and the `return []` below meant its #6854 diff
    # was never reached -- a new BINDING NOW, the one event ruling 193 names, woke nobody. Measured
    # at 8c6edb162: two polls, a new BINDING NOW on the second, zero discovery, printed nothing and
    # exited `no change in 600s across 0 watched PR(s)`. That is the idle lane, which is precisely
    # the lane that arms a watcher.
    seeding = "seeded" not in state
    response = runner(
        query_text(known, repo, ruling_issue, label_groups),
        query_variables(known, repo, ruling_issue, label_groups),
    )
    data = response.get("data") or {}
    _check_windows(data, label_groups)
    _check_explicit(data, prs)
    _check_ruling(data, ruling_issue)
    after: dict = snapshot(data, known)
    before: dict = {"prs": dict(state.get("prs") or {}), "ruling": state.get("ruling")}
    _check_read_gone_null(before, after)

    lines: list[str] = []
    watched = list(known)
    for number, group in discovered(data, label_groups).items():
        if number in before["prs"] or _read(after["prs"].get(number)):
            continue  # already watched, or read this very poll (a --pr that also matches a label)
        after["prs"][number] = {UNREAD: list(group)}
        watched.append(number)
        if not seeding:
            lines.append(_watch_line(number, group))
    for number in known:
        old = before["prs"].get(number)
        if isinstance(old, dict) and UNREAD in old and number in after["prs"]:
            fields = after["prs"][number]
            if fields is None:
                pass  # asked and null: inaccessible. It stays UNREAD -- see the carry below.
            elif fields["state"] in ("MERGED", "CLOSED"):
                # Discovery saw this PR OPEN one poll ago, so the change happened under the watcher.
                lines.append(f"#{number} " + _state_line(fields["state"]))
    for number in watched:
        # A PR asked about but answered null keeps the REASON it is watched instead of becoming an
        # unknown: it may answer next poll, and the line it eventually prints names the label that
        # pulled it in. A fresh registration is already carried by ``after`` -- restoring from
        # ``before`` for every not-yet-read entry used to wipe the group off it, because the group
        # lives in this poll's entry and `before` has no entry at all.
        if after["prs"].get(number) is None and UNREAD in (before["prs"].get(number) or {}):
            after["prs"][number] = before["prs"][number]
    after["watched"] = watched
    # Set on BOTH exits, so the next poll's `seeding` is False whatever the watched set looks like
    # -- including the empty one above. The seed poll still returns [] before reaching it.
    after["seeded"] = True
    if seeding:
        state.update(after)
        return []
    lines.extend(diff_lines(watched, ruling_issue, before, after))
    state.clear()
    state.update(after)
    return lines


def _from(login: str | None) -> str:
    return "" if not login else f" from {login}"


def _genuine_additions(
    before: Sequence[tuple], after: Sequence[tuple], *, truncated: bool
) -> list[tuple]:
    """Items of ``after`` that are real arrivals, not window bookkeeping. Position, not membership.

    The window is asked `last: EVENT_WINDOW` and comes back OLDEST-FIRST (measured on #6854: 721
    comments, the 100 returned run 05:55:29Z .. 09:21:47Z strictly ascending), so a comment that
    JUST ARRIVED sits ABOVE every id the two polls share, while a comment GitHub BACKFILLS -- an
    old one re-entering at the BOTTOM when the newest comment is deleted and the window's top edge
    shrinks to make room -- sits BELOW them. Announcing a backfill as `new` is the round-two bug
    (a deletion announcing an addition) seen from the other end of the window, on the channel whose
    whole value is that the agent trusts it, and it fires on BOTH channels: a false `new comment`
    for a PR watcher, a false `new BINDING NOW` for every lane on #6854. So position against the
    shared ids picks the word: strictly above every shared id is a real arrival.

    Membership alone is sound only when NEITHER window was truncated. The first version of this
    guard asked only about the window in hand -- "a window shorter than the cap returned every
    existing item, so nothing could backfill" -- and that is true of the CURRENT poll and false of
    the comparison being made, because a backfill is judged against the PREVIOUS snapshot: if the
    previous window was FULL, truncation existed then, and an id that had aged out of it re-enters
    the moment deletions shrink the window below the cap. Measured at `81057a51b`: seed the full
    window of a 150-comment PR, then delete the 60 newest -- the shrink answered short and printed
    50 `new comment` lines for comments older than everything on screen. Hence `truncated` is ORed
    across BOTH windows, and the caller must derive each side from the RAW window length, not a
    filtered view: truncation is a property of the connection, not of how many rows matched a
    filter.

    A truncated window that shares NO id with the previous one has no anchor, and position without
    an anchor cannot be proved: measured at the same head, two consecutive full windows with zero
    shared ids (a `last: 100` bulk-deleted on a >200-comment thread) passed every fresh id and
    printed 100 `new comment` lines with nothing added. There the NEW side says nothing and the
    vanished side still speaks, so the watcher is never silent about what happened.
    """
    old_ids = {item[0] for item in before}
    new_ids = {item[0] for item in after}
    fresh = [item for item in after if item[0] not in old_ids]
    if not truncated:
        return fresh  # neither window truncated: every id that exists was in one of the two polls
    anchor = old_ids & new_ids
    if not anchor:
        return []  # nothing shared: position is unprovable, so announce no arrival
    idx = {item[0]: i for i, item in enumerate(after)}
    top_shared = max(idx[i] for i in anchor)
    return [item for item in fresh if idx[item[0]] > top_shared]


def _event_lines(
    prefix: str, noun: str, after: Sequence[tuple], before: Sequence[tuple]
) -> list[str]:
    """One line per item that appeared OR vanished, naming its author, never its body.

    The old shape printed "new review"/"new comment" whenever the two sets differed, and a
    DELETION makes them differ: seeding comments `(1, 2, 3)` and answering the next poll with
    `(1, 2)` printed ``#7175 new comment`` while naming no author, because the item it searched for
    -- an id in ``after`` that is not in ``before`` -- does not exist in that direction. So the
    watcher announced an addition that had not happened, on the channel whose whole value is that
    the agent trusts it when it prints. A deleted comment or review is not one of ruling 193's six
    change classes, and this file already resolved that tension once in ``_state_line`` (a reopen
    is not a class either, and the line names it anyway) -- naming what moved beats announcing its
    opposite or hiding the difference behind the word "new".
    """
    # NEW side -- filtered through the backfill guard (see _genuine_additions), then phrased. The
    # guard's `truncated` flag is the OR of BOTH windows' raw lengths: a backfill is an id that was
    # absent LAST poll because the window truncated then, so a short window in hand does not prove
    # the previous snapshot held everything (round five's finding 1).
    lines = [
        f"{prefix}new {noun}{_from(item[1])}"
        for item in _genuine_additions(
            before,
            after,
            truncated=len(before) >= EVENT_WINDOW or len(after) >= EVENT_WINDOW,
        )
    ]
    old_ids = {item[0] for item in before}
    new_ids = {item[0] for item in after}
    # A full window cannot name a deletion. These connections are asked `last: EVENT_WINDOW`, so on
    # a PR with more comments than the window holds, ONE new comment pushes the oldest item out --
    # the id vanishes from the response without anything being deleted. Reproduced against this
    # `check()` seam: 100 ids, then the window slid by one, and the poll printed
    # `#7175 deleted comment from u1` beside the genuine `new comment from u101`. When the window
    # came back SHORTER than its cap, GitHub returned every item that exists, so a vanished id can
    # only have been deleted and the precise word is earned. When it came back FULL, the cause is
    # unobservable from here, so the line says what was observed -- present, then absent -- instead
    # of asserting the half of it the API did not answer. Suppressing the line was the other option
    # and is worse: a real deletion on a long PR would then be invisible, and the guard `_check_windows`
    # uses for discovery (raise, refuse the poll) would make every long lane PR unwatchable.
    vanished = [item for item in before if item[0] not in new_ids]
    verdict = "deleted" if len(after) < EVENT_WINDOW else "missing"
    lines += [f"{prefix}{verdict} {noun}{_from(item[1])}" for item in vanished]
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
    label_groups: Sequence[Sequence[str]] = (),
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
            # The count is the watcher's OWN set, not the `--pr` flags: label discovery may have
            # added PRs after arming, and a headline that names the launch count instead of the
            # watched count would misreport what sat here for the whole lifetime.
            watched = state.get("watched")
            total = len(watched) if watched else len(prs)
            return 0, [f"no change in {int(lifetime)}s across {total} watched PR(s)"]
        try:
            lines = check(
                runner,
                state,
                repo=repo,
                prs=prs,
                ruling_issue=ruling_issue,
                label_groups=label_groups,
            )
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


def gh_result(proc: subprocess.CompletedProcess) -> dict:
    """Turn one ``gh api graphql`` result into a payload -- or raise, never swallow.

    Split out of ``gh_runner`` for the same reason ``gh_args`` and ``parse_args`` are: the rule
    lives here, the side effect does not. This is the ONLY place a GitHub GraphQL ``errors``
    response can become visible, and it is the sole real trigger for ``watch``'s max-errors exit,
    so returning ``{}`` instead of raising would make a broken watch look like a quiet one -- the
    silently-empty class this module keeps meeting (an Int passed with ``-f`` matches nothing and
    returns no error). Pinned by a test and by a campaign mutant, not by the injected seam alone.
    """
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip()[:400])
    payload: dict = json.loads(proc.stdout)
    if payload.get("errors"):
        raise RuntimeError(str(payload["errors"])[:400])
    return payload


def gh_runner(query: str, variables: dict) -> dict:
    """The production seam: one ``gh api graphql`` call, parsed by ``gh_result``."""
    return gh_result(
        subprocess.run(gh_args(query, variables), capture_output=True, text=True, check=False)
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """The CLI, split out of ``main`` so the flag-to-group mapping is testable without a poll."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument(
        "--pr",
        action="append",
        type=int,
        dest="prs",
        default=[],
        help="a PR to watch regardless of its labels; repeat for each one",
    )
    parser.add_argument("--lane", default="", help="discover PRs labelled lane:<this>")
    parser.add_argument("--cell", default="", help="and cell:<this> (the ops lane splits)")
    parser.add_argument(
        "--review-label",
        action="append",
        dest="review_labels",
        default=[],
        help="discover PRs labelled with this review label; repeat for each one",
    )
    parser.add_argument("--ruling-issue", type=int, default=RULING_ISSUE)
    parser.add_argument("--interval", type=float, default=60.0, help="seconds between polls")
    parser.add_argument("--lifetime", type=float, default=3600.0, help="seconds before quitting")
    parser.add_argument("--max-errors", type=int, default=3)
    args = parser.parse_args(argv)
    # Dedup --pr here, in FIRST-OCCURRENCE order. `--pr 7175 --pr 7175` is what lane.md step 6's
    # own sentence produces when one PR is both yours and a review row, and the flag is harmless
    # until the query text declares $p7175 twice -- the API then answers variableNotUnique (live,
    # measured) on EVERY poll, and the watcher dies at max_errors with an "API failure" line about
    # a malformed arm. The watch of one PR is one alias.
    args.prs = list(dict.fromkeys(args.prs))
    if not args.prs and not label_groups(args.lane, args.cell, args.review_labels):
        parser.error(
            "nothing to watch: give a --pr, or --lane/--cell/--review-label to discover by"
        )
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    rc, lines = watch(
        gh_runner,
        {},
        lambda: datetime.now(UTC),
        time.sleep,
        repo=args.repo,
        prs=list(args.prs),
        ruling_issue=args.ruling_issue,
        label_groups=label_groups(args.lane, args.cell, args.review_labels),
        interval=args.interval,
        lifetime=args.lifetime,
        max_errors=args.max_errors,
    )
    for line in lines:
        print(line)  # this line on stdout is the CLI's entire contract with the agent
    return rc


if __name__ == "__main__":
    sys.exit(main())
