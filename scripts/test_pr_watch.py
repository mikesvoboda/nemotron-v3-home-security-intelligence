#!/usr/bin/env python3
"""Tests for scripts/uplevel/pr_watch.py (ruling 193), with no network.

Run explicitly; outside testpaths (like every scripts/test_*.py gate suite):

    uv run python -m pytest scripts/test_pr_watch.py -q

One seam, as `test_lane_tick.py` does for `lane_tick.build`: the watcher takes a runner callable
`run(query, variables) -> dict` that stands for the single batched GraphQL call a poll makes, plus
an injected clock and sleeper. Nothing here patches a module global or reaches the network; a
runner asked for something nobody scripted raises, so a new read shows up as a failing test instead
of a live API call. The tests pin what ruling 193 requires:

- one GraphQL query per poll, and the query never uses the `search` API (its 30-per-minute limit is
  shared by every agent on the owner's token);
- exactly one line naming the PR and the change, on: a new head commit, a check conclusion, a
  review, a comment, a label change, a merge or a close, and a new `BINDING NOW` on #6854;
- comment BODIES are never printed -- only who posted and where;
- the first poll seeds state and reports nothing (an agent arms the watcher mid-tick; the changes
  it already saw are not news);
- a transient API error does not end the watch; `max_errors` consecutive failures end it with an
  error line, so silence never stands in for success;
- a bounded lifetime ends it with a "no change" line, so the agent re-arms.
"""

from __future__ import annotations

import ast
import importlib.util
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "uplevel" / "pr_watch.py"
CAMPAIGN = REPO_ROOT / "scripts" / "r193-mutation-campaign.py"
AGENTS_DOC = REPO_ROOT / "scripts" / "uplevel" / "AGENTS.md"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


watch = _load("pr_watch", SCRIPT)

NOW = datetime(2026, 10, 15, 16, 0, 0, tzinfo=UTC)
REPO = "o/r"
PR = 7168
RULING_ISSUE = 6854


class Run:
    """Scripted stand-in for the one GraphQL call a poll makes.

    Each poll consumes one scripted response (a dict) or raises one scripted exception. The
    runner records every query it was asked to run, so the query-shape tests read the recorded
    text rather than a source grep. ``calls`` is the poll count the tests assert on.
    """

    def __init__(self, *responses):
        self.responses = list(responses)
        self.queries: list[str] = []
        self.variables: list[dict] = []
        self.calls = 0

    def __call__(self, query, variables):
        self.calls += 1
        self.queries.append(query)
        self.variables.append(variables)
        if not self.responses:
            raise AssertionError(f"unscripted read: poll {self.calls} has no response")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def pr_node(
    number=PR,
    *,
    head="a" * 40,
    state="OPEN",
    labels=("lane:backend", "review:ops-a"),
    checks=(("CI Gate (Required Checks)", "SUCCESS", "COMPLETED"),),
    raw_checks=(),
    check_total=None,
    reviews=(),
    comments=(),
):
    """One PullRequest node in the shape the query parses: the fields the watcher diffs."""
    return {
        "number": number,
        "headRefOid": head,
        "state": state,
        "labels": {"nodes": [{"name": n} for n in labels]},
        # the rollup's checks live under contexts.nodes, NOT nodes -- verified against the live
        # schema (introspection: StatusCheckRollup.fields = commit/contexts/id/state). A fixture
        # using `nodes` here would match a wrong parser and both would fail on the first poll.
        # `raw_checks` appends VERBATIM context nodes for the shapes `checks` cannot express -- a
        # StatusContext is `{context, state}`, not `{name, conclusion, status}`, and its in-flight
        # value is the STRING "PENDING" (a CheckRun's is a null conclusion + a `status` field), so
        # only a raw node can pin the clause that filters that string.
        "statusCheckRollup": {
            "contexts": {
                # `totalCount` defaults to the node count -- "nothing is hidden" -- because the
                # field is what lets `_truncated` tell a short window (proof every check exists)
                # from a full one that dropped runs. A fixture that omitted it would seed
                # truncation into every test that builds a node.
                "totalCount": len(checks) + len(raw_checks) if check_total is None else check_total,
                "nodes": [{"name": n, "conclusion": c, "status": s} for n, c, s in checks]
                + list(raw_checks),
            }
        },
        "reviews": {"nodes": [{"id": i, "author": {"login": "mikesvoboda"}} for i in reviews]},
        "comments": {
            "nodes": [{"id": i, "author": {"login": u}, "body": b} for i, u, b in comments]
        },
    }


def issue_node(ids, bodies=None):
    """The #6854 node: comment ids with bodies (the watcher keys on the BINDING NOW marker)."""
    bodies = bodies or {}
    return {
        "number": RULING_ISSUE,
        "comments": {
            "nodes": [
                {
                    "id": i,
                    "author": {"login": "mikesvoboda"},
                    "body": bodies.get(i, "routine status"),
                }
                for i in ids
            ]
        },
    }


def discovery_node(numbers, total=None):
    """One `pullRequests(labels: …)` connection: the numbers it matched, and the full count.

    `totalCount` is a real field here (measured by introspection: PullRequestConnection.fields =
    edges/nodes/pageInfo/totalCount) and it is the only way the watcher can tell a FULL window
    from an EMPTY one -- 100 nodes could be everything, or the newest 100 of 300.
    """
    return {
        "nodes": [{"number": n} for n in numbers],
        "totalCount": total if total is not None else len(numbers),
    }


def envelope(prs, ruling_ids=None, ruling_bodies=None, found=None):
    """The single GraphQL response envelope, in the shape GitHub actually returns it.

    The aliases live INSIDE the one `repository` selection set (`data.repository.p7168`), because
    GraphQL has no top-level `pullRequest` field to alias. Getting this right is the point of the
    helper: a flat fixture would let a parser that misses the nesting pass every test and then
    find nothing in production.

    `found` maps a discovery alias (`a`, `b`, …) to the connection it returns, so a test can say
    "this label group matched these PRs" the same way it says what a watched PR looks like.
    """
    repository = {f"p{p['number']}": p for p in prs}
    for alias, connection in (found or {}).items():
        repository[alias] = connection
    if ruling_ids is not None:
        repository["issue"] = issue_node(ruling_ids, ruling_bodies)
    return {"data": {"repository": repository}}


# --------------------------------------------------------------------------- change detection


def seed(prs=(PR,)) -> dict:
    """Run the first poll against a green, known state and keep the seeded state dict."""
    response = envelope(
        [pr_node(n) for n in prs],
        ruling_ids=[1],
        ruling_bodies={1: "BINDING NOW: 45 live"},
    )
    runner = Run(response)
    state: dict = {}
    lines = watch.check(runner, state, repo=REPO, prs=list(prs), ruling_issue=RULING_ISSUE)
    assert lines == [], "the first poll seeds state; nothing is news yet"
    assert runner.calls == 1
    return state


def second(runner, state):
    return watch.check(runner, state, repo=REPO, prs=[PR], ruling_issue=RULING_ISSUE)


def test_new_head_commit_is_reported():
    state = seed()
    moved = envelope(
        [pr_node(PR, head="b" * 40)], ruling_ids=[1], ruling_bodies={1: "BINDING NOW: 45 live"}
    )
    lines = second(Run(moved), state)
    assert len(lines) == 1, lines
    assert lines[0].startswith(f"#{PR} ")
    assert "head" in lines[0] and ("b" * 7) in lines[0]


def test_check_conclusion_change_is_reported():
    state = seed()
    red = envelope(
        [pr_node(PR, checks=(("CI Gate (Required Checks)", "FAILURE", "COMPLETED"),))],
        ruling_ids=[1],
        ruling_bodies={1: "BINDING NOW: 45 live"},
    )
    lines = second(Run(red), state)
    assert len(lines) == 1, lines
    assert "CI Gate" in lines[0] and "FAILURE" in lines[0].upper()


def test_check_still_running_is_not_reported():
    state = seed()
    inflight = envelope(
        [
            pr_node(
                PR,
                checks=(("CI Gate (Required Checks)", None, "IN_PROGRESS"),),
            )
        ],
        ruling_ids=[1],
        ruling_bodies={1: "BINDING NOW: 45 live"},
    )
    assert second(Run(inflight), state) == [], "a check without a conclusion is not a conclusion"


def test_new_review_is_reported():
    state = seed()
    reviewed = envelope(
        [pr_node(PR, reviews=("RV_9",))],
        ruling_ids=[1],
        ruling_bodies={1: "BINDING NOW: 45 live"},
    )
    lines = second(Run(reviewed), state)
    assert len(lines) == 1 and lines[0].startswith(f"#{PR} ")
    assert "review" in lines[0].lower()


def test_new_comment_is_reported_without_its_body():
    state = seed()
    body = "SECRET-BODY-MUST-NOT-REACH-A-LINE"
    commented = envelope(
        [pr_node(PR, comments=(("C_9", "mikesvoboda", body),))],
        ruling_ids=[1],
        ruling_bodies={1: "BINDING NOW: 45 live"},
    )
    lines = second(Run(commented), state)
    assert len(lines) == 1 and "comment" in lines[0].lower()
    assert body not in lines[0]


def test_a_vanished_comment_on_a_full_window_says_missing_not_deleted():
    """A comment that aged out of a FULL `last: EVENT_WINDOW` window was not deleted.

    Reproduced against the shipped `check()`: a window of exactly EVENT_WINDOW ids, then the window
    sliding by one -- one comment arrives (id 101), the oldest leaves the response (id 1), nothing is
    deleted -- and the poll printed `['#7175 new comment from u101', '#7175 deleted comment from u1']`.
    The line asserted a cause the API never answered: on a PR with more comments than the window, an
    eviction and a deletion look identical. A window SHORTER than the cap held every comment that
    exists, so there the precise word is earned (see the test above); a FULL window may only report
    what it saw -- present, then absent.
    """
    ids = [f"C_{i}" for i in range(1, watch.EVENT_WINDOW + 1)]
    full = envelope(
        [pr_node(PR, comments=tuple((i, f"u{i}", "routine") for i in ids))],
        ruling_ids=[1],
        ruling_bodies={1: "BINDING NOW: 45 live"},
    )
    state: dict = {}
    assert watch.check(Run(full), state, repo=REPO, prs=[PR], ruling_issue=RULING_ISSUE) == [], (
        "the seed poll installs the full window and reports nothing"
    )
    slid = [*ids[1:], f"C_{watch.EVENT_WINDOW + 1}"]
    moved = envelope(
        [pr_node(PR, comments=tuple((i, f"u{i}", "routine") for i in slid))],
        ruling_ids=[1],
        ruling_bodies={1: "BINDING NOW: 45 live"},
    )
    lines = watch.check(Run(moved), state, repo=REPO, prs=[PR], ruling_issue=RULING_ISSUE)
    assert any("new comment from uC_101" in ln for ln in lines), lines
    gone = [ln for ln in lines if "missing comment" in ln]
    assert len(gone) == 1 and "from uC_1" in gone[0], lines
    assert not any("deleted" in ln for ln in lines), (
        f"a full window cannot name a deletion: {lines}"
    )


def test_a_backfilled_comment_on_a_full_window_is_not_announced_as_new():
    """A comment GitHub BACKFILLS into a full window is not a new comment.

    Reproduced against the shipped `check()` at head `78dbf9b60` (before the fix): seed the full
    window `C_1..C_100`, slide it one (`C_2..C_101`, the genuine append prints), then DELETE `C_101`.
    `last: 100` re-answers with `C_1..C_100` -- `C_1` was aged out last poll and is back -- and the
    poll printed ``#7175 new comment from uC_1``. Nothing new happened; a comment was DELETED, and the
    oldest survivor re-entered at the bottom of the window. That is the round-two finding (a deletion
    announcing an addition) seen from the OTHER end of the window, and it is the line the watcher's
    whole premise puts the agent's trust in. The guard reads POSITION: the window is oldest-first
    (measured live on #6854, 721 comments returned strictly ascending), a real arrival sits ABOVE every
    shared id, a backfill re-enters BELOW the last shared one. The genuine append still prints -- that
    is what the assertion on poll 2 pins, and the reason the fix is positional and not a blanket
    "full window prints no new" gate (which would silence the signal the watcher exists for).
    """
    ids = [f"C_{i}" for i in range(1, watch.EVENT_WINDOW + 1)]

    def env(id_list):
        return envelope(
            [pr_node(PR, comments=tuple((i, f"u{i}", "routine") for i in id_list))],
            ruling_ids=[1],
            ruling_bodies={1: "BINDING NOW: 45 live"},
        )

    state: dict = {}
    assert (
        watch.check(Run(env(ids)), state, repo=REPO, prs=[PR], ruling_issue=RULING_ISSUE) == []
    ), "the seed poll installs the full window and reports nothing"
    slid = [*ids[1:], f"C_{watch.EVENT_WINDOW + 1}"]
    lines = watch.check(Run(env(slid)), state, repo=REPO, prs=[PR], ruling_issue=RULING_ISSUE)
    assert any("new comment from uC_101" in ln for ln in lines), f"a genuine append prints: {lines}"
    backfill = ids[:]  # C_101 deleted -> last:100 back-fills C_1; nothing new exists
    lines = watch.check(Run(env(backfill)), state, repo=REPO, prs=[PR], ruling_issue=RULING_ISSUE)
    assert not any("new comment" in ln for ln in lines), f"a backfill is not an arrival: {lines}"
    assert any("missing comment from uC_101" in ln for ln in lines), lines


def test_a_full_window_that_shrinks_to_short_reports_no_arrivals():
    """A window that goes FULL -> SHORT re-opens the backfill bug unless BOTH windows are consulted.

    The guard this replaces asked only about the window in hand: "a window shorter than the cap
    returned every existing item, so nothing could backfill." That is true of the CURRENT poll and
    false of the COMPARISON, because a backfill is an id that was absent LAST poll -- and if last
    poll's window was FULL, truncation existed then, so ids had aged out and are free to re-enter the
    moment deletions shrink the window below the cap. Measured at `81057a51b` against the shipped
    `check()`: a 150-comment PR seeded with the full window `C_51..C_150`, then the 60 newest
    DELETED, so `last: 100` answers all 90 survivors `C_1..C_90` -- and the poll printed 50
    `new comment from uC_1..` lines for comments older than everything that had been on screen.
    Nothing was added; 60 comments were deleted. So `truncated` is the OR of both windows' raw
    lengths. The same measurement on the #6854 channel is the sibling test; each channel keeps its
    own copy of the predicate and both needed the same repair.
    """
    W = watch.EVENT_WINDOW
    all_ids = [f"C_{i}" for i in range(1, 151)]

    def env(id_list):
        return envelope(
            [pr_node(PR, comments=tuple((i, f"u{i}", "routine") for i in id_list))],
            ruling_ids=[1],
            ruling_bodies={1: "BINDING NOW: 45 live"},
        )

    state: dict = {}
    assert (
        watch.check(Run(env(all_ids[-W:])), state, repo=REPO, prs=[PR], ruling_issue=RULING_ISSUE)
        == []
    ), "the seed poll installs the full window and reports nothing"
    # The 60 newest are deleted: 90 comments remain, all of them returned, and 50 ids that had aged
    # out of the full window are back at the BOTTOM of it.
    lines = watch.check(
        Run(env(all_ids[:90])), state, repo=REPO, prs=[PR], ruling_issue=RULING_ISSUE
    )
    assert not any("new comment" in ln for ln in lines), (
        f"a shrink re-enters aged-out ids; none of them is an arrival: {lines}"
    )
    assert sum("deleted comment from" in ln for ln in lines) == 60, (
        f"the deletions are what really happened and still get named: {lines}"
    )
    # A genuine arrival AFTER the shrink still prints, which is what stops the fix being a blanket
    # "short window says nothing" gate.
    lines = watch.check(
        Run(env([*all_ids[:90], "C_200"])), state, repo=REPO, prs=[PR], ruling_issue=RULING_ISSUE
    )
    assert [ln for ln in lines if "new comment" in ln] == ["#7168 new comment from uC_200"], lines


def test_a_window_turnover_with_no_shared_id_announces_no_arrival():
    """Two full windows sharing NO id have no anchor, and position without an anchor proves nothing.

    The positional rule compares each fresh id to the highest position shared by the two polls. With
    zero shared ids the max had no argument and fell back to -1, so EVERY fresh id satisfied
    `idx > top_shared`: measured at `81057a51b`, a >200-comment PR whose whole `last: 100` window was
    bulk-deleted answered a full window of ids that had never been seen and printed 100 `new comment`
    lines -- `new=100 missing=100`, nothing added. An unanchored comparison cannot distinguish an
    arrival from a re-entry, so the NEW side stays silent and the vanished side still speaks (100
    `missing comment` lines): the watcher never claims a change it cannot support and is never silent
    about the half it did observe.
    """
    W = watch.EVENT_WINDOW

    def env(id_list):
        return envelope(
            [pr_node(PR, comments=tuple((i, f"u{i}", "routine") for i in id_list))],
            ruling_ids=[1],
            ruling_bodies={1: "BINDING NOW: 45 live"},
        )

    before = [f"C_{i}" for i in range(151, 151 + W)]  # a full window of a 250-comment PR
    after = [f"C_{i}" for i in range(51, 51 + W)]  # disjoint: the 100 newest were bulk-deleted
    assert len(set(before) & set(after)) == 0, "the scenario needs zero shared ids to mean anything"
    state: dict = {}
    assert (
        watch.check(Run(env(before)), state, repo=REPO, prs=[PR], ruling_issue=RULING_ISSUE) == []
    )
    lines = watch.check(Run(env(after)), state, repo=REPO, prs=[PR], ruling_issue=RULING_ISSUE)
    assert not any("new comment" in ln for ln in lines), (
        f"an unanchored window cannot prove an arrival: {lines}"
    )
    assert sum("missing comment from" in ln for ln in lines) == W, (
        f"the vanished side is still reported: {lines}"
    )


def test_a_backfilled_binding_on_a_full_ruling_window_is_not_announced_as_new():
    """The same hazard on the #6854 ruling channel, where a false line wakes EVERY lane.

    A lane that already carried a `BINDING NOW` out treats a second report of it as a no-op (ruling
    40), so the cost here is a false wake, not a wrong fact -- but the false wake is exactly the noise
    the digest is built to avoid. Reproduced against shipped `check()`: a full ruling window whose
    newest comment carries a BINDING (so it is reported), then that newest comment DELETED, which
    back-fills an older comment that also binds -- a ruling every lane acted on days ago -- and the
    naive set diff announces it as `new BINDING NOW`. The arrival test runs on the RAW comment window
    (`window_ids`), where ~100 shared ids anchor the position, so a filtered binding list cannot lose
    the anchor. A BINDING that genuinely arrives at the new end, and one that was EDITED into
    existence on an id already in the window, both still print (pinned by the second assertion).
    """
    W = watch.EVENT_WINDOW
    ids = [f"R_{i}" for i in range(1, W + 1)]
    BIND = "BINDING NOW: 12 live"

    def env(id_list, binding_ids):
        return envelope(
            [pr_node(PR)],
            ruling_ids=id_list,
            ruling_bodies=dict.fromkeys(binding_ids, BIND),
        )

    state: dict = {}
    # poll 1: full window; an old binding near the bottom, the newest ruling at the very top.
    first = env(ids, {ids[0], ids[-1]})
    assert watch.check(Run(first), state, repo=REPO, prs=[PR], ruling_issue=RULING_ISSUE) == []
    # poll 2: the TOP comment is DELETED, so `last: 100` back-fills the next-oldest id -- and it
    # re-enters at the BOTTOM (the window is oldest-first), carrying a BINDING from days ago.
    backfilled = ["R_0", *ids[:-1]]
    lines = watch.check(
        Run(env(backfilled, {ids[0], "R_0"})), state, repo=REPO, prs=[PR], ruling_issue=RULING_ISSUE
    )
    assert not any("new BINDING" in ln for ln in lines), (
        f"a back-filled BINDING re-wakes every lane onto a ruling already carried out: {lines}"
    )


def test_a_shrinking_ruling_window_re_wakes_no_lane():
    """The #6854 channel has its own copy of the predicate and needed the same repair.

    The full-window ruling pin above asks whether the window in hand is full; the shrink case shows
    why that is the wrong question. Measured at `81057a51b` against the shipped `check()`: 100
    binding comments fill the window, then 40 of the newest are deleted, so the window answers SHORT
    with every survivor -- and the 40 ids that had aged out of the FULL previous window re-enter at
    the bottom. The old fast path consulted only the new window, saw it short, concluded "everything
    that exists was returned", and printed 50 `new BINDING NOW` lines (the fixture re-seeds the whole
    aged-out block as bindings) -- every one of them a wake for every lane in the repo onto a ruling
    UR-40 had already made a no-op. The cost here is not a wrong fact but exactly the false wake
    the digest exists to prevent, which is why this channel gets its own pin rather than a note.
    """
    W = watch.EVENT_WINDOW
    BIND = "BINDING NOW: 12 live"
    seed = [f"R_{i}" for i in range(51, 151)]  # a FULL window: 100 of a 150-comment issue

    def env(window, binding_ids):
        return envelope(
            [pr_node(PR)], ruling_ids=window, ruling_bodies=dict.fromkeys(binding_ids, BIND)
        )

    state: dict = {}
    assert (
        watch.check(
            Run(env(seed, set(seed))), state, repo=REPO, prs=[PR], ruling_issue=RULING_ISSUE
        )
        == []
    ), "the seed poll installs the full binding window and stays silent"
    # 60 newest deleted -> 90 comments exist, all returned (window SHORT), and the 50 ids that aged
    # out of the full window are back at its bottom, each still carrying its old BINDING.
    shrunk = [f"R_{i}" for i in range(1, 91)]
    lines = watch.check(
        Run(env(shrunk, set(shrunk))), state, repo=REPO, prs=[PR], ruling_issue=RULING_ISSUE
    )
    assert not any("new BINDING" in ln for ln in lines), (
        f"aged-out rulings re-entering on a shrink are not new rulings: {lines}"
    )
    # A ruling that genuinely arrives after the shrink still wakes, so this is not a blanket gate.
    lines = watch.check(
        Run(env([*shrunk, "R_999"], {*(set(shrunk) | {"R_999"})})),
        state,
        repo=REPO,
        prs=[PR],
        ruling_issue=RULING_ISSUE,
    )
    assert any("new BINDING NOW (comment R_999" in ln for ln in lines), lines


def test_an_anchorless_ruling_window_turnover_wakes_no_lane():
    """The no-anchor rule needs its own pin on #6854, where the false line is a repo-wide wake.

    The shrink test above shares 40 ids between its two windows, so it never reaches the no-anchor
    clause -- and the campaign proved that by removing the clause and staying green (`ruling-anchorless-turnover-reads-as-new`
    ESCAPED with all 60 tests passing). So this scenario is the disjoint one: a FULL binding window,
    then a FULL window sharing NO id with it (the newest 100 rulings bulk-deleted on a long issue).
    With no shared id the positional comparison has nothing to compare against, and the old `-1`
    fallback called every binding an arrival -- 100 `new BINDING NOW` lines, each one waking every
    lane in the repo onto a ruling no lane has seen and most of them carried out days ago (UR-40).
    An unanchored window proves nothing, so the channel says nothing; the slide that follows, whose
    ids ARE shared, proves the silence is about the missing anchor and not about the channel.
    """
    W = watch.EVENT_WINDOW
    BIND = "BINDING NOW: 12 live"
    seed = [f"R_{i}" for i in range(151, 251)]  # full window of a 250-comment ruling issue
    after = [f"R_{i}" for i in range(1, 101)]  # disjoint: the newest 100 were bulk-deleted

    def env(window, binding_ids):
        return envelope(
            [pr_node(PR)], ruling_ids=window, ruling_bodies=dict.fromkeys(binding_ids, BIND)
        )

    assert len(set(seed) & set(after)) == 0, "the scenario needs zero shared ids to mean anything"
    state: dict = {}
    assert (
        watch.check(
            Run(env(seed, set(seed))), state, repo=REPO, prs=[PR], ruling_issue=RULING_ISSUE
        )
        == []
    )
    lines = watch.check(
        Run(env(after, set(after))), state, repo=REPO, prs=[PR], ruling_issue=RULING_ISSUE
    )
    assert not any("new BINDING" in ln for ln in lines), (
        f"an unanchored ruling window cannot prove a new ruling: {lines}"
    )
    # The next poll shares 99 ids, so the same code reports the one genuine arrival.
    slid = [*after[1:], "R_999"]
    lines = watch.check(
        Run(env(slid, set(slid))), state, repo=REPO, prs=[PR], ruling_issue=RULING_ISSUE
    )
    assert [ln for ln in lines if "new BINDING NOW" in ln], (
        f"with an anchor, a real arrival wakes lanes again: {lines}"
    )
    assert sum("new BINDING NOW" in ln for ln in lines) == 1, lines


def test_a_binding_that_arrives_or_was_edited_into_existence_still_prints():
    """Positive control the backfill guard must not break: two real ruling events still report.

    (a) a BINDING appended at the new end of the window -- the ordinary case; (b) a routine comment
    EDITED to carry the marker: same id, already in the window last poll, so it is "shared" by
    position yet genuinely new as an EVENT (a body edit is not a window move). A positional rule that
    only fires on ids absent from last poll would silence (b), and a blanket full-window gate would
    silence (a). Both must survive.
    """
    W = watch.EVENT_WINDOW
    ids = [f"R_{i}" for i in range(1, W + 1)]
    BIND = "BINDING NOW: 12 live"

    def env(window, binding_ids):
        return envelope(
            [pr_node(PR)], ruling_ids=window, ruling_bodies=dict.fromkeys(binding_ids, BIND)
        )

    state: dict = {}
    assert (
        watch.check(Run(env(ids, {ids[0]})), state, repo=REPO, prs=[PR], ruling_issue=RULING_ISSUE)
        == []
    )
    # (a) a fresh BINDING ARRIVES: the window slides, the new id is absent from last poll and sits
    # at the new end. (A static window would make it an EDIT, not an arrival -- the branch matters.)
    slid = [*ids[1:], "R_new"]
    lines = watch.check(
        Run(env(slid, {ids[1], "R_new"})), state, repo=REPO, prs=[PR], ruling_issue=RULING_ISSUE
    )
    assert any("new BINDING" in ln for ln in lines), f"a genuine new BINDING prints: {lines}"
    # (b) an id already in the window flips from routine to BINDING (an edit; position unchanged,
    # the window identical). A rule keyed only on "id absent last poll" would silence this.
    lines = watch.check(
        Run(env(slid, {ids[1], "R_new", ids[50]})),
        state,
        repo=REPO,
        prs=[PR],
        ruling_issue=RULING_ISSUE,
    )
    assert any("new BINDING" in ln for ln in lines), f"a BINDING edited into place prints: {lines}"


def test_a_deleted_comment_is_reported_as_deleted_not_as_new():
    """A vanished comment must not announce an addition.

    The diff used to fire on ANY set difference and then search ``after`` for an id missing from
    ``before`` -- which in the delete direction finds nothing, so the line read ``#7175 new
    comment`` naming no author while the real event was the opposite. Reproduced before the fix:
    seed ids ``(1, 2, 3)``, answer the next poll with ``(1, 2)``, get ``['#7175 new comment']``.
    A deletion is not one of ruling 193's six change classes, and `_state_line` already settled how
    this file handles a non-class event on a channel it watches: name it rather than announce its
    opposite. Bodies are still never printed -- only who and what.
    """
    state = seed()
    three = envelope(
        [
            pr_node(
                PR,
                comments=(("C_1", "u1", "first"), ("C_2", "u2", "second"), ("C_3", "u3", "third")),
            )
        ],
        ruling_ids=[1],
        ruling_bodies={1: "BINDING NOW: x"},
    )
    added = second(Run(three), state)
    assert len(added) == 3 and all("new comment" in line for line in added), added
    two = envelope(
        [pr_node(PR, comments=(("C_1", "u1", "first"), ("C_2", "u2", "second")))],
        ruling_ids=[1],
        ruling_bodies={1: "BINDING NOW: x"},
    )
    lines = second(Run(two), state)
    assert lines == [f"#{PR} deleted comment from u3"], lines
    assert not any("third" in line for line in lines), "the vanished body stays out of the line"


def test_a_deleted_review_is_reported_as_deleted_not_as_new():
    """The same defect on the review channel, where it printed ``new review`` for a retraction."""
    state = seed()
    both = envelope(
        [pr_node(PR, reviews=("RV_1", "RV_2"))],
        ruling_ids=[1],
        ruling_bodies={1: "BINDING NOW: x"},
    )
    assert len(second(Run(both), state)) == 2
    one = envelope(
        [pr_node(PR, reviews=("RV_1",))],
        ruling_ids=[1],
        ruling_bodies={1: "BINDING NOW: x"},
    )
    lines = second(Run(one), state)
    assert lines == [f"#{PR} deleted review from mikesvoboda"], lines


def test_label_change_is_reported():
    state = seed()
    relabelled = envelope(
        [pr_node(PR, labels=("lane:backend",))],
        ruling_ids=[1],
        ruling_bodies={1: "BINDING NOW: 45 live"},
    )
    lines = second(Run(relabelled), state)
    assert len(lines) == 1 and "label" in lines[0].lower()
    assert "review:ops-a" in lines[0]


def test_merge_is_reported():
    state = seed()
    merged = envelope(
        [pr_node(PR, state="MERGED")],
        ruling_ids=[1],
        ruling_bodies={1: "BINDING NOW: 45 live"},
    )
    lines = second(Run(merged), state)
    assert len(lines) == 1 and "merged" in lines[0].lower()


def test_close_is_reported():
    state = seed()
    closed = envelope(
        [pr_node(PR, state="CLOSED")],
        ruling_ids=[1],
        ruling_bodies={1: "BINDING NOW: 45 live"},
    )
    lines = second(Run(closed), state)
    assert len(lines) == 1 and "clos" in lines[0].lower()


def test_a_pr_that_reopens_prints_reopened_not_closed():
    """A state change the watcher already reports must name the state it reached, not its opposite.

    A reopen is not one of ruling 193's six change classes, but the STATE CHANGE is: the line
    exists because the state moved, and ``else "closed"`` printed "closed" for every non-merge,
    so a reopened PR reported the opposite of the event on the one line an agent acts on.
    """
    state = seed()
    closed = envelope(
        [pr_node(PR, state="CLOSED")],
        ruling_ids=[1],
        ruling_bodies={1: "BINDING NOW: 45 live"},
    )
    lines = second(Run(closed), state)
    assert len(lines) == 1 and "clos" in lines[0].lower()
    reopened = envelope(
        [pr_node(PR, state="OPEN")],
        ruling_ids=[1],
        ruling_bodies={1: "BINDING NOW: 45 live"},
    )
    lines = second(Run(reopened), state)
    assert len(lines) == 1 and "reopen" in lines[0].lower()


def test_a_merged_pr_that_reopens_prints_reopened_too():
    """The other direction, because `else "closed"` covered it too: MERGED -> OPEN."""
    state = seed()
    merged = envelope(
        [pr_node(PR, state="MERGED")],
        ruling_ids=[1],
        ruling_bodies={1: "BINDING NOW: 45 live"},
    )
    lines = second(Run(merged), state)
    assert len(lines) == 1 and "merged" in lines[0].lower()
    reopened = envelope(
        [pr_node(PR, state="OPEN")],
        ruling_ids=[1],
        ruling_bodies={1: "BINDING NOW: 45 live"},
    )
    lines = second(Run(reopened), state)
    assert len(lines) == 1 and "reopen" in lines[0].lower()


def test_new_binding_now_is_reported():
    state = seed()
    binding = envelope(
        [pr_node(PR)],
        ruling_ids=[1, 2],
        ruling_bodies={1: "BINDING NOW: 45 live", 2: "BINDING NOW: 46 live"},
    )
    lines = second(Run(binding), state)
    assert len(lines) == 1
    assert lines[0].startswith(f"#{RULING_ISSUE} ") and "BINDING NOW" in lines[0]


def test_a_binding_phrase_mentioned_off_the_first_line_is_not_a_new_record():
    """UR-40 binds a record whose FIRST LINE carries the marker, so a mere mention is silent.

    The live case is #6854 comment `6180424930`, whose first line is ``URGENT PATH · coordinator
    stale again`` and whose status prose counts "42 BINDING NOW rows in window" on a later line
    (verified at that id: one occurrence, none on the first line). A substring match on the whole
    body treats that as a new binding record, which is the opposite of what the watcher is for: a
    line it prints has to mean a record binds.
    """
    state = seed()
    mentioned = envelope(
        [pr_node(PR)],
        ruling_ids=[1, 2],
        ruling_bodies={
            1: "BINDING NOW: 45 live",
            2: "URGENT PATH · coordinator stale again\n\n"
            "State this leaves: my tick acts on the filtered sweep directly "
            "(42 BINDING NOW rows in window, all already carried).",
        },
    )
    lines = second(Run(mentioned), state)
    assert lines == [], lines


def test_a_label_only_watcher_still_reports_a_new_binding_now():
    """A watcher that discovers NOTHING still leaves its seed state, so #6854 is still watched.

    The shape is the idle lane: armed by `--lane` alone, no `--pr`, and its lane label currently
    matches no open PR. `seeding` keyed on emptiness (`not state["prs"]`) stayed True on every
    poll of exactly this watcher, and the seed poll's `return []` ran before the ruling diff, so a
    new `BINDING NOW` — the one event ruling 193 names — printed nothing and the run ended
    `no change in 600s across 0 watched PR(s)`. Every other BINDING NOW test seeds with a non-empty
    `prs`, so none of them could see it.
    """
    empty = envelope(
        [], ruling_ids=[1], ruling_bodies={1: "routine"}, found={"a0": discovery_node([])}
    )
    binding = envelope(
        [],
        ruling_ids=[1, 2],
        ruling_bodies={1: "routine", 2: "BINDING NOW: ruling 199 binds now"},
        found={"a0": discovery_node([])},
    )
    state: dict = {}
    runner = Run(empty, binding)
    first = watch.check(
        runner, state, repo=REPO, prs=[], ruling_issue=RULING_ISSUE, label_groups=[LANE_OPS]
    )
    assert first == [], "the seed poll reports nothing"
    assert state["prs"] == {}, "the lane genuinely has nothing routed to it"
    later = watch.check(
        runner,
        state,
        repo=REPO,
        prs=[],
        ruling_issue=RULING_ISSUE,
        label_groups=[LANE_OPS],
    )
    assert len(later) == 1, later
    assert later[0].startswith(f"#{RULING_ISSUE} ") and "BINDING NOW" in later[0], later


def test_a_non_binding_new_comment_on_the_ruling_issue_is_silent():
    state = seed()
    other = envelope(
        [pr_node(PR)],
        ruling_ids=[1, 2],
        ruling_bodies={1: "BINDING NOW: 45 live", 2: "routine status comment"},
    )
    assert second(Run(other), state) == []


def test_one_graphql_call_per_poll_and_never_the_search_api():
    state = seed()
    runner = Run(envelope([pr_node(PR)], ruling_ids=[1], ruling_bodies={1: "BINDING NOW: 45 live"}))
    watch.check(runner, state, repo=REPO, prs=[PR], ruling_issue=RULING_ISSUE)
    assert runner.calls == 1, "one batched GraphQL query per poll"
    assert "query" in runner.queries[0]
    # the variables the query declares are the ones the poll sends, or every alias reads null.
    assert runner.variables[0] == watch.query_variables([PR], REPO, RULING_ISSUE)
    assert "search(" not in runner.queries[0].replace(" ", ""), (
        "ruling 193: never the search API -- its 30-per-minute limit is shared by every agent"
    )


def test_the_query_asks_for_each_watched_pr_under_one_repository_root():
    """Aliases nest inside the repository node -- there is no top-level pullRequest field.

    This is also the fixture's own control: ``envelope`` puts the nodes at
    ``data.repository.p<NNN>`` because that is what GitHub returns, and this asserts the query
    asks for them the same way. If the two ever disagree, the parse reads nulls and the change
    tests go red here instead of passing in CI and finding nothing in production.
    """
    query = watch.query_text([7168, 7175], REPO, RULING_ISSUE)
    assert query.count("repository(owner:") == 1, "one repository root, aliased children"
    assert "p7168: pullRequest(number: $p7168)" in query
    assert "p7175: pullRequest(number: $p7175)" in query
    assert "issue(number: $ri)" in query


def test_the_new_end_is_watched_not_the_old_end():
    """Every connection the watcher reads for NEW items must be a `last:` window.

    Found live, not in the fixture: #6854 has 646 comments, so `comments(first: 100)` returned the
    OLDEST hundred -- zero BINDING NOW entries, `hasNextPage` true -- while `comments(last: 100)`
    held 30. A fixture with 1-2 comments can never show this, so the guard is on the query text.
    Shape-specific, not a bare `first:` substring: `labels(first: 20)` is correct because a PR's
    labels are a small bounded SET, whereas comments/reviews/check-runs grow without bound and the
    watcher only cares about their newest entries.
    """
    query = watch.query_text([PR], REPO, RULING_ISSUE)
    for connection in ("comments(", "reviews(", "contexts("):
        for line in query.splitlines():
            if connection in line:
                assert "last:" in line, f"{connection!r} must read the new end: {line.strip()}"


def test_graphql_variables_use_the_flag_gh_actually_accepts():
    """`gh api` has no --var, and a String flag on an Int variable is rejected by GitHub.

    Found by the first live call -- the argv sits outside the tested runner seam, so it is pinned
    here directly instead of by memory of which flag works.
    """
    args = watch.gh_args("query { x }", watch.query_variables([PR], REPO, RULING_ISSUE))
    assert args[:3] == ["gh", "api", "graphql"]
    assert "--var" not in args, "gh api has no --var flag"
    # pair each flag with the "key=value" that follows it -> {key: flag that carried it}.
    # The -f carrying the query itself is keyed "query", which is not a variable -- skip it.
    carried = {
        args[i + 1].split("=", 1)[0]: a
        for i, a in enumerate(args)
        if a in ("-f", "-F") and not args[i + 1].startswith("query=")
    }
    assert carried.get("p7168") == "-F", "the Int PR number goes on the typed flag"
    assert carried.get("ri") == "-F"
    assert carried.get("owner") == "-f", "String variables go on -f"
    # every variable is present exactly once, on the flag matching its type.
    variables = watch.query_variables([PR], REPO, RULING_ISSUE)
    assert set(carried) == set(variables), "no variable dropped or doubled"
    for key, value in variables.items():
        want = "-F" if isinstance(value, int) and not isinstance(value, bool) else "-f"
        assert carried[key] == want, f"{key}={value!r} on {carried[key]}, wanted {want}"


# ---------------------------------------------------------------- label discovery (ruling 193)


# One connection per label, because `labels:` is OR (see label_groups). The lane set on its
# own is what most discovery tests exercise; OPS_A is the three a cell-A agent arms with.
LANE_OPS = ["lane:ops"]
CELL_A = ["cell:a"]
REVIEW_A = ["review:ops-a"]
OPS_A = [LANE_OPS, CELL_A, REVIEW_A]


def test_label_groups_are_the_lane_cell_and_review_sets():
    """The three label kinds ruling 193 names, as three separate connections.

    Each label gets its OWN connection because the connection's `labels:` argument is OR, measured
    against the live API: `lane:ops` (82 PRs) together with `lane:docs` (56) -- two labels no PR can
    carry at once -- came back as ONE query of 138 with an empty intersection. AND would have
    returned 0. Merging lane and cell into one connection therefore cannot narrow anything, and
    because a watch line names the labels whose connection matched, a merged group would print
    `cell:a` on PRs that do not carry it.
    """
    assert watch.label_groups("ops", "a", ["review:ops-a"]) == [LANE_OPS, ["cell:a"], REVIEW_A]
    assert watch.label_groups("ops", "", ["review:ops-a"]) == [LANE_OPS, REVIEW_A]
    assert watch.label_groups("", "", []) == [], "no labels given: nothing to discover"
    assert watch.label_groups("backend", "b", []) == [["lane:backend"], ["cell:b"]]


def test_a_labeled_pr_is_discovered_and_named_as_newly_watched():
    """Poll 1 seeds the set silently; a PR that joins the set later gets its one line.

    The seed poll must NOT print a line per PR it discovers -- an agent arms the watcher with six
    matching PRs already there, and six lines would read as six events.
    """
    state = {}
    first = Run(
        envelope(
            [pr_node(PR)],
            ruling_ids=[1],
            ruling_bodies={1: "BINDING NOW: x"},
            found={"a0": discovery_node([PR]), "a1": discovery_node([])},
        )
    )
    assert (
        watch.check(
            first,
            state,
            repo=REPO,
            prs=[],
            ruling_issue=RULING_ISSUE,
            label_groups=[LANE_OPS, REVIEW_A],
        )
        == []
    ), "the seed poll is silent"
    joined = Run(
        envelope(
            [pr_node(PR), pr_node(7176)],
            ruling_ids=[1],
            ruling_bodies={1: "BINDING NOW: x"},
            found={"a0": discovery_node([PR]), "a1": discovery_node([7176])},
        )
    )
    lines = watch.check(
        joined,
        state,
        repo=REPO,
        prs=[],
        ruling_issue=RULING_ISSUE,
        label_groups=[LANE_OPS, REVIEW_A],
    )
    assert len(lines) == 1, lines
    assert lines[0].startswith("#7176 ") and "watch" in lines[0].lower(), lines
    assert "review:ops-a" in lines[0], "the line names the label group that pulled it in"
    # and the state keeps WHY it is watched, not just that it is: the carry-forward pass below the
    # registration used to overwrite this entry with a group-less UNREAD, so the reason printed once
    # was gone from the state that decides what to do next poll.
    assert state["prs"][7176][watch.UNREAD] == ["review:ops-a"], state["prs"][7176]


def test_a_pr_two_labels_match_is_watched_for_both_reasons():
    """A PR in two connections gets BOTH labels on its line, not the first one.

    This is the ordinary case, not an edge: #7175 carries `lane:ops` AND `cell:a`, so the two
    connections answer with the same number. `labels:` is OR (measured: 82 + 56 = 138 in one query
    with an empty intersection), so one connection per label means one PR lands in several.
    Naming only the first would print a line that omits a match the response proved, and the state
    entry -- which decides what the next poll does with the PR -- would carry half the reason.
    """
    state = seed(prs=(PR,))  # poll 1 read PR, so poll 2 is not seeding
    joined = Run(
        envelope(
            [pr_node(PR), pr_node(7175)],
            ruling_ids=[1],
            ruling_bodies={1: "BINDING NOW: x"},
            # the same number under both aliases, exactly as the live API answers it
            found={"a0": discovery_node([PR, 7175]), "a1": discovery_node([7175])},
        )
    )
    lines = watch.check(
        joined,
        state,
        repo=REPO,
        prs=[PR],
        ruling_issue=RULING_ISSUE,
        label_groups=[LANE_OPS, CELL_A],
    )
    assert lines == ["#7175 watching (label lane:ops+cell:a)"], lines
    assert state["prs"][7175][watch.UNREAD] == ["lane:ops", "cell:a"], state["prs"][7175]


def test_a_discovered_pr_reports_its_events_once_seeded():
    """Newly watched means seeded first, so its FIRST reported change is a real one.

    Discovery gives only numbers; the head/check/comment fields come from the `p<n>` alias, which
    next poll asks for. A watcher that reported the first poll's whole state as "changes" would
    print a stale head and every existing check verdict the moment a PR got labelled.
    """
    state = {}
    watch.check(
        Run(
            envelope(
                [pr_node(PR)],
                ruling_ids=[1],
                ruling_bodies={1: "BINDING NOW: x"},
                found={"a0": discovery_node([PR])},
            )
        ),
        state,
        repo=REPO,
        prs=[],
        ruling_issue=RULING_ISSUE,
        label_groups=[LANE_OPS],
    )
    # poll 2: 7176 appears; only its number is known, so its fields are not read yet -> no fields,
    # no diff, and its number is the one line.
    watch.check(
        Run(
            envelope(
                [pr_node(PR)],
                ruling_ids=[1],
                ruling_bodies={1: "BINDING NOW: x"},
                found={"a0": discovery_node([PR, 7176])},
            )
        ),
        state,
        repo=REPO,
        prs=[],
        ruling_issue=RULING_ISSUE,
        label_groups=[LANE_OPS],
    )
    # poll 3: its fields are asked for and match what the previous poll's node said -> still silent.
    asked = state["watched"]
    assert PR in asked and 7176 in asked, "both are now in the watched set"
    third = Run(
        envelope(
            [pr_node(PR), pr_node(7176)],
            ruling_ids=[1],
            ruling_bodies={1: "BINDING NOW: x"},
            found={"a0": discovery_node([PR, 7176])},
        )
    )
    assert (
        watch.check(
            third,
            state,
            repo=REPO,
            prs=[],
            ruling_issue=RULING_ISSUE,
            label_groups=[LANE_OPS],
        )
        == []
    )
    # poll 4: the head moves -> reported.
    moved = envelope(
        [pr_node(PR), pr_node(7176, head="e" * 40)],
        ruling_ids=[1],
        ruling_bodies={1: "BINDING NOW: x"},
        found={"a0": discovery_node([PR, 7176])},
    )
    lines = watch.check(
        Run(moved),
        state,
        repo=REPO,
        prs=[],
        ruling_issue=RULING_ISSUE,
        label_groups=[LANE_OPS],
    )
    assert len(lines) == 1 and lines[0].startswith("#7176 "), lines


def test_a_merged_pr_stays_watched_after_it_leaves_the_open_set():
    """The watched set only grows, because a merge takes the PR out of the discovery query.

    `states: [OPEN]` is required -- unfiltered, `labels: ["lane:ops"]` matched 82 PRs against 6 open
    ones (measured 2026-10-15) and would build that many field aliases into one poll. But a PR
    merges OUT of an OPEN-only connection, and a watcher that followed the set each poll would stop
    asking for the node and never report the merge -- the one event the lane waits for. So
    discovery adds; nothing removes.
    """
    state = {}
    watch.check(
        Run(
            envelope(
                [pr_node(PR)],
                ruling_ids=[1],
                ruling_bodies={1: "BINDING NOW: x"},
                found={"a0": discovery_node([PR])},
            )
        ),
        state,
        repo=REPO,
        prs=[],
        ruling_issue=RULING_ISSUE,
        label_groups=[LANE_OPS],
    )
    gone = Run(
        envelope(
            [pr_node(PR, state="MERGED")],
            ruling_ids=[1],
            ruling_bodies={1: "BINDING NOW: x"},
            found={"a0": discovery_node([])},
        )
    )
    lines = watch.check(
        gone, state, repo=REPO, prs=[], ruling_issue=RULING_ISSUE, label_groups=[LANE_OPS]
    )
    assert len(lines) == 1 and "merged" in lines[0].lower(), lines


def test_discovery_stays_inside_one_query_and_never_the_search_api():
    """Label groups cost aliases, not round trips -- ruling 193's limit is per poll.

    Guarded against the two shapes that would pass a test and fail the ruling: a second call per
    group, and a `search(type: PULL_REQUEST)` query, whose 30-per-minute limit the whole programme
    shares on the owner's token.
    """
    state = {}
    runner = Run(
        envelope(
            [pr_node(PR)],
            ruling_ids=[1],
            ruling_bodies={1: "BINDING NOW: x"},
            found={"a0": discovery_node([PR]), "a1": discovery_node([])},
        )
    )
    watch.check(
        runner,
        state,
        repo=REPO,
        prs=[PR],
        ruling_issue=RULING_ISSUE,
        label_groups=[LANE_OPS, REVIEW_A],
    )
    assert runner.calls == 1, "both label groups resolve inside the poll's one query"
    query = runner.queries[0]
    assert "search(" not in query.replace(" ", "")
    assert query.count("repository(owner:") == 1, "still one repository root"
    assert "a0: pullRequests(" in query and "a1: pullRequests(" in query
    assert "states: [OPEN]" in query, (
        "an unfiltered lane query matched 82 PRs against 6 open ones (measured 2026-10-15)"
    )
    assert "field: UPDATED_AT" in query, (
        "IssueOrderField, not PullRequestOrderField: UPDATED_DESC is rejected outright --"
        " measured: Argument 'field' on InputObject 'IssueOrder' has an invalid value"
    )
    # DESC, and the mutation battery is what caught this unpinned: ASC fills a full window with the
    # LEAST recently updated matches and cuts the ones an agent is waiting on. The truncation guard
    # fires in the same situation, but it is the backstop, not the design -- the window itself has
    # to hold the newest activity.
    for line in query.splitlines():
        if "orderBy" in line:
            assert "direction: DESC" in line, f"discovery must order newest-first: {line.strip()}"
    # Sliced to the discovery connection, NOT `"totalCount" in query`: the field name now appears
    # TWICE in this query (the discovery connection and, since round six's fix, the check
    # `contexts`), so a whole-query substring is answered by either one and deleting the discovery
    # ask alone stayed green -- my own campaign caught that escape, which is round six's
    # identical-rendering hole met from the other side. `query_text` emits every discovery group
    # before every PR alias, so the first `pullRequest(number:` is the boundary; the assert below
    # keeps that ordering load-bearing rather than assumed.
    head, sep, _rest = query.partition("pullRequest(number:")
    assert sep, "no PR alias to slice on, so the discovery section has no boundary"
    assert "totalCount" in head, "a full discovery window must be distinguishable from an empty one"


def test_label_strings_ride_as_variables_and_never_in_the_query_text():
    """Two measured reasons the labels cannot be inlined or sent as a JSON array.

    `-F 'l0=["lane:ops"]'` returned `{"nodes": []}` with NO error -- a silently empty watch that
    reads as a quiet tick -- while a per-element `$a0_0: String!` on `-f` matched correctly. Keeping
    the value out of the text also means a label never has to survive GraphQL string escaping.
    """
    query = watch.query_text([PR], REPO, RULING_ISSUE, OPS_A)
    variables = watch.query_variables([PR], REPO, RULING_ISSUE, OPS_A)
    for i, (label,) in enumerate(OPS_A):
        assert label not in query, f"{label!r} is inlined; it must be a variable"
        assert variables[f"a{i}_0"] == label, f"{label!r} missing or mis-keyed"
        assert f"$a{i}_0: String!" in query, f"{label!r} undeclared"
        assert f"labels: [$a{i}_0]" in query, (
            f"{label!r} must be the ONLY label in its connection: `labels:` is OR (measured, 82+56"
            f" = 138 with an empty intersection), so a merged connection cannot narrow anything and"
            f" its watch line would name a label the PR does not carry"
        )
    assert all(isinstance(v, (str, int)) for v in variables.values()), (
        "no list values: gh's -F JSON array form silently matches nothing"
    )
    args = watch.gh_args(query, variables)
    carried = {
        args[i + 1].split("=", 1)[0]: a
        for i, a in enumerate(args)
        if a in ("-f", "-F") and not args[i + 1].startswith("query=")
    }
    assert carried["a0_0"] == "-f", "a String label on -f; -F would JSON-encode it"


def test_a_full_discovery_window_raises_instead_of_looking_quiet():
    """100 nodes with totalCount 300 means 200 PRs went unseen -- that must not be silence.

    `totalCount` is a real field (introspected: PullRequestConnection = edges/nodes/pageInfo/
    totalCount). Raising routes through the loop's existing error path, so the agent sees an error
    line and a non-zero exit rather than a tick that watched nothing.
    """
    state = {}
    full = discovery_node(list(range(1, 101)), total=300)
    runner = Run(
        envelope(
            [pr_node(PR)], ruling_ids=[1], ruling_bodies={1: "BINDING NOW: x"}, found={"a0": full}
        )
    )
    try:
        watch.check(
            runner,
            state,
            repo=REPO,
            prs=[PR],
            ruling_issue=RULING_ISSUE,
            label_groups=[LANE_OPS],
        )
    except RuntimeError as exc:
        assert "300" in str(exc) and "100" in str(exc), exc
    else:
        raise AssertionError("a truncated discovery window must raise, not report nothing")


def test_an_explicit_pr_answered_null_raises_instead_of_looking_calm():
    """A null for a number the agent TYPED is a broken watch, not a quiet tick.

    `snapshot` stores None for an absent `p<number>` and `diff_lines` skips a pair whose either side
    is unreadable, so a head change that straddles the null window never prints -- and it never
    prints twice, because the next poll's `before` IS the null snapshot. Nothing recovers it: label
    discovery will never hand back a number the agent already passed to `--pr`. Reproduced before
    the guard: four polls (head `a`…, null, head `b`…, steady) printed `[] [] [] []`.
    """
    state = seed()
    deaf = envelope([], ruling_ids=[1], ruling_bodies={1: "BINDING NOW: x"})
    # "explicitly watched", not just the number: _check_read_gone_null ALSO names #7168, and a
    # seeded state means its message is the one this poll raises -- so a `#<n>` match passed
    # under the `explicit-null-skipped` mutant once the new guard existed. The phrase is the
    # author's signature; the number only says somebody noticed.
    with pytest.raises(RuntimeError, match="explicitly watched"):
        second(Run(deaf), state)


def test_an_explicit_pr_answered_null_on_its_first_read_raises():
    """The case `_check_read_gone_null` cannot cover: nothing was ever read, so nothing "came back".

    The read-gone-null guard needs a PRIOR read, and on the first poll there is none -- without
    `_check_explicit` this poll just seeds a None and returns []. That gap is how
    `explicit-null-skipped` escaped the campaign after the new guard landed: the older tests seed
    `#7168` first, so their null poll trips the NEW guard, which also names the PR, and both tests
    passed under the mutant while `_check_explicit` itself went unobserved. From an empty state the
    raise this test asserts has exactly one possible author.
    """
    deaf = envelope([], ruling_ids=[1], ruling_bodies={1: "BINDING NOW: x"})
    with pytest.raises(RuntimeError, match="explicitly watched"):
        watch.check(Run(deaf), {}, repo=REPO, prs=[PR], ruling_issue=RULING_ISSUE)


def test_a_transient_null_for_an_explicit_pr_costs_one_error_not_the_change():
    """The guard's routing, measured end to end: the straddling head change still gets printed.

    Same envelope on every poll but the middle one, which answers `#7168` as null. Poll 2 raises, so
    `watch` credits one error and `state` KEEPS the last good snapshot instead of overwriting it with
    a null -- which is what makes the loss repairable: poll 3 diffs head `a` against head `b` and the
    watcher reports the change it would otherwise have swallowed. A prolonged null is the other half
    of the story and `test_repeated_failures_exit_with_an_error_line` pins that path.
    """
    state = seed()
    same = envelope([pr_node(PR)], ruling_ids=[1], ruling_bodies={1: "BINDING NOW: x"})
    moved = envelope(
        [pr_node(PR, head="b" * 40)], ruling_ids=[1], ruling_bodies={1: "BINDING NOW: x"}
    )
    deaf = envelope([], ruling_ids=[1], ruling_bodies={1: "BINDING NOW: x"})
    runner = Run(same, deaf, moved)
    sim = Sim()
    rc, lines = watch.watch(
        runner,
        state,
        sim.clock,
        sim.sleep,
        repo=REPO,
        prs=[PR],
        ruling_issue=RULING_ISSUE,
        interval=60,
        lifetime=3600,
        max_errors=3,
    )
    assert rc == 0 and len(lines) == 1 and "head" in lines[0], lines
    assert runner.calls == 3, "one error credit, then the change on the next good poll"


def test_a_discovered_pr_answered_null_keeps_its_watch_reason_and_still_reports_its_merge():
    """The UNREAD carry-forward is live behavior, and it only serves DISCOVERED PRs.

    A PR that joined by label match, was registered UNREAD, and is answered null on its first field
    read must (a) keep the label that pulled it in, and (b) still report a merge once it answers.
    Without the carry line the entry is None on both sides of the next poll, so neither the
    merged-before-read branch nor `diff_lines` can fire, and the merge of a PR the watcher was
    explicitly watching prints nothing. `_check_explicit` does NOT cover this: it guards only the
    numbers an agent typed, and a discovered PR can legitimately leave the OPEN set between polls.
    """
    state: dict = {}
    watch.check(
        Run(
            envelope(
                [],  # discovery matched it, but its fields were not in this poll's aliases
                ruling_ids=[1],
                ruling_bodies={1: "BINDING NOW: x"},
                found={"a0": discovery_node([PR])},
            )
        ),
        state,
        repo=REPO,
        prs=[],
        ruling_issue=RULING_ISSUE,
        label_groups=[LANE_OPS],
    )
    # The seed poll names it; its fields are still unread.
    assert state["prs"][PR] == {watch.UNREAD: ["lane:ops"]}, state["prs"][PR]
    # Poll 2 asks for its fields and GitHub answers null: the watch REASON survives.
    watch.check(
        Run(
            envelope(
                [],
                ruling_ids=[1],
                ruling_bodies={1: "BINDING NOW: x"},
                found={"a0": discovery_node([])},
            )
        ),
        state,
        repo=REPO,
        prs=[],
        ruling_issue=RULING_ISSUE,
        label_groups=[LANE_OPS],
    )
    assert state["prs"][PR] == {watch.UNREAD: ["lane:ops"]}, (
        "the carry-forward keeps the label group that registered it"
    )
    # Poll 3: it answers, MERGED. The change happened under the watcher's interest, so it prints.
    lines = watch.check(
        Run(
            envelope(
                [pr_node(PR, state="MERGED")],
                ruling_ids=[1],
                ruling_bodies={1: "BINDING NOW: x"},
                found={"a0": discovery_node([])},
            )
        ),
        state,
        repo=REPO,
        prs=[],
        ruling_issue=RULING_ISSUE,
        label_groups=[LANE_OPS],
    )
    assert len(lines) == 1 and "merged" in lines[0].lower(), lines


def test_a_pr_read_on_an_earlier_poll_then_answered_null_raises():
    """The carry-forward's own boundary, on the DISCOVERED channel: read-once, then null.

    The test above pins a PR answered null while still UNREAD -- its fields were never lost, only
    never yet read, so silence is right and the label group survives. This is the other side: a
    discovered PR that HAS been read, so the carry no longer applies (`_check_explicit` cannot help
    either -- it guards only numbers typed as `--pr`). `diff_lines` skips a pair whose either side is
    unreadable, and the next poll's `before` IS the null snapshot, so a head change straddling the
    null window would be lost silently and for good. Measured before the guard: four scripted polls
    (read, null, null, head moved) printed `[] [] [] []` and the state entry ended as the moved
    fields -- the change had passed unheard. `_check_read_gone_null` raises on the null instead.
    """
    state: dict = {}
    watch.check(
        Run(
            envelope(
                [],
                ruling_ids=[1],
                ruling_bodies={1: "BINDING NOW: x"},
                found={"a0": discovery_node([PR])},
            )
        ),
        state,
        repo=REPO,
        prs=[],
        ruling_issue=RULING_ISSUE,
        label_groups=[LANE_OPS],
    )
    assert state["prs"][PR] == {watch.UNREAD: ["lane:ops"]}
    # The PR answers: its fields are now READ, and the entry is no longer an UNREAD placeholder.
    watch.check(
        Run(
            envelope(
                [pr_node(PR)],
                ruling_ids=[1],
                ruling_bodies={1: "BINDING NOW: x"},
                found={"a0": discovery_node([])},
            )
        ),
        state,
        repo=REPO,
        prs=[],
        ruling_issue=RULING_ISSUE,
        label_groups=[LANE_OPS],
    )
    assert watch._read(state["prs"][PR]), "poll 2 read its fields"
    with pytest.raises(RuntimeError, match=f"#{PR}"):
        watch.check(
            Run(
                envelope(
                    [],
                    ruling_ids=[1],
                    ruling_bodies={1: "BINDING NOW: x"},
                    found={"a0": discovery_node([])},
                )
            ),
            state,
            repo=REPO,
            prs=[],
            ruling_issue=RULING_ISSUE,
            label_groups=[LANE_OPS],
        )


def test_a_read_pr_answered_null_once_still_reports_its_straddling_change():
    """End to end: the raise costs one credit and the change it protects still prints.

    The guard's whole value is in this routing, so it is pinned through `watch`, not at `check`. A
    raise leaves `state` on the LAST GOOD snapshot -- `check` clears `state` only on a clean return,
    so the null poll never overwrites it. That is what makes the loss repairable: poll 4 diffs head
    `a` against head `b` and reports the change that the silent-skip version swallowed for good.
    """
    state: dict = {}
    same = envelope(
        [pr_node(PR)],
        ruling_ids=[1],
        ruling_bodies={1: "BINDING NOW: x"},
        found={"a0": discovery_node([])},
    )
    moved = envelope(
        [pr_node(PR, head="b" * 40)],
        ruling_ids=[1],
        ruling_bodies={1: "BINDING NOW: x"},
        found={"a0": discovery_node([])},
    )
    deaf = envelope(
        [], ruling_ids=[1], ruling_bodies={1: "BINDING NOW: x"}, found={"a0": discovery_node([])}
    )
    # Seed by label (so the PR is on the DISCOVERED channel this guard serves), then read it.
    register = envelope(
        [], ruling_ids=[1], ruling_bodies={1: "BINDING NOW: x"}, found={"a0": discovery_node([PR])}
    )
    runner = Run(register, same, deaf, moved)
    sim = Sim()
    rc, lines = watch.watch(
        runner,
        state,
        sim.clock,
        sim.sleep,
        repo=REPO,
        prs=[],
        ruling_issue=RULING_ISSUE,
        label_groups=[LANE_OPS],
        interval=60,
        lifetime=3600,
        max_errors=3,
    )
    assert rc == 0 and len(lines) == 1 and "head" in lines[0], lines
    assert runner.calls == 4, (
        "one error credit on the null poll, then the change on the next good one"
    )


def test_a_status_context_still_running_is_no_verdict_but_a_reached_one_is():
    """The rollup's OTHER node type, whose in-flight value is a STRING, now has a fixture.

    `pr_watch.py` reads `... on StatusContext { context state }` and `_checks` filters
    `conclusion != "PENDING"`, because a StatusContext is in flight as the string `state: "PENDING"`
    -- a CheckRun is in flight as a null `conclusion` plus a `status` field, which is what every
    other fixture in this file emits. So no `{name, conclusion, status}` node can reach that clause:
    the campaign's `inflight-reported` mutant (which drops the whole condition) was caught through
    the null-conclusion path, and replacing the string `"PENDING"` with `"NOPE"` passed 48/48 -- the
    clause had no witness. `raw_checks` supplies a real `{context, state}` node. Both halves, so the
    filter cannot be satisfied by dropping the branch: a PENDING context prints NOTHING, a SUCCESS
    one prints.
    """
    state = seed()
    pending = envelope(
        [pr_node(PR, raw_checks=[{"context": "external/ci", "state": "PENDING"}])],
        ruling_ids=[1],
        ruling_bodies={1: "BINDING NOW: x"},
    )
    assert second(Run(pending), state) == [], (
        "a context still running is not a verdict it has not reached"
    )
    landed = envelope(
        [pr_node(PR, raw_checks=[{"context": "external/ci", "state": "SUCCESS"}])],
        ruling_ids=[1],
        ruling_bodies={1: "BINDING NOW: x"},
    )
    lines = second(Run(landed), state)
    assert len(lines) == 1 and "external/ci" in lines[0] and "SUCCESS" in lines[0], lines


def test_a_null_ruling_issue_raises_instead_of_looking_calm():
    """A poll that cannot see #6854 must not seed a channel that never compares again.

    `snapshot` stores `state["ruling"] = None` when the `issue` node comes back null, and
    `diff_lines` then compares only `if old_ruling and new_ruling` -- so a SEED poll answered null
    leaves the watcher permanently unable to report a BINDING NOW, with zero errors, for its whole
    lifetime. The discovery path has `_check_windows` for that shape of silence; the ruling channel
    is the one ruling 193 says a lane must never miss, so it gets the same guard. The trigger
    (issue deleted or made inaccessible) is inference, not observed live; the SILENCE it causes is
    what's pinned here, and it is a property of the code, not of GitHub.
    """
    state = {}
    runner = Run(envelope([pr_node(PR)], ruling_ids=None))  # the `issue` node is absent
    try:
        watch.check(runner, state, repo=REPO, prs=[PR], ruling_issue=RULING_ISSUE)
    except RuntimeError as exc:
        assert str(RULING_ISSUE) in str(exc), exc
    else:
        raise AssertionError("a null ruling node must raise, not seed a permanently deaf channel")


def _query_asks() -> list[tuple[str, str]]:
    """Every `(first|last): N` the query builder sends, as (argument, size) pairs.

    Read off the BUILD FUNCTION'S SYNTAX, not off the rendered query, and not with grep: the
    connection sizes that matter are the ones a guard later compares a length against, and a
    hand-typed `last: 100` renders byte-identically to `last: {EVENT_WINDOW}` at the constant's
    value -- so no observation of the RENDERED text can tell the two apart. Parsing the AST sees
    the difference (one is a bare number in the string, one is an interpolated name), and it
    ignores comments and docstrings, which is why grep and regex-over-the-file were the wrong
    instruments here: query_text's own comments say `last: 100` while the code asks something else.
    """
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "query_text")
    asks: list[tuple[str, str]] = []
    for node in ast.walk(fn):
        pieces: list[str] = []
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            pieces = [node.value]
        elif isinstance(node, ast.JoinedStr):  # an f-string: interpolate names as {NAME}
            for part in node.values:
                if isinstance(part, ast.Constant):
                    pieces.append(part.value)
                elif isinstance(part, ast.FormattedValue):
                    inner = part.value
                    name = inner.id if isinstance(inner, ast.Name) else "?"
                    pieces.append("{" + name + "}")
        else:
            continue
        # JOINED, not per-piece: an f-string splits `last: {EVENT_WINDOW}` into a literal ending at
        # "last: " and a separate FormattedValue, so matching piece-by-piece finds nothing at all for
        # every interpolated ask -- the first version of this helper returned 2 of the 6 asks and both
        # were the hand-typed ones, which is exactly backwards for a guard meant to catch typing.
        text = "".join(pieces)
        for kind, size in re.findall(r"\b(first|last):\s*([A-Za-z0-9_]+|\{[A-Za-z_]+\})", text):
            asks.append((kind, size))
    return asks


def test_window_size_is_bounded_by_a_named_constant():
    """Every connection whose LENGTH a guard compares is asked by constant, never by typed digits.

    The discovery window and the event window are both load-bearing twice over: the query asks for
    that many nodes, and a guard later asks whether the connection came back FULL -- `_check_windows`
    against DISCOVERY_WINDOW, `snapshot`'s `window_full` and `_event_lines`' deleted-vs-missing
    verdict against EVENT_WINDOW. Two numbers, one property. The version of this pin that asserted
    `f"comments(last: {EVENT_WINDOW})" in query` could not tell which connection satisfied it, and
    round six measured the hole: retyping #6854's ask to `last: 99` or `last: 101` left all 61 tests
    green, because the PR channel's rendering -- identical bytes -- answered for it.
    """
    asks = _query_asks()
    # Positive control on the census itself: a parse that found nothing would satisfy every
    # `not in` below and pass vacuously, so the total is pinned too (6 asks in query_text today).
    assert len(asks) == 6, f"census found {len(asks)} asks: {asks}"
    # sorted(), not a fixed sequence: ast.walk is breadth-first and interleaves the two groups, so
    # the order is an artifact of the parse, not a property worth pinning. Sorting keeps the COUNT
    # (which is the point) while ignoring which line the parser reached first.
    # 1. Graded asks must name a constant. Four EVENT_WINDOW (reviews, comments, #6854 rulings, and
    #    the check `contexts` -- whose fullness `_truncated` now grades against that same constant,
    #    which is what moved it out of group 2) + one DISCOVERY_WINDOW (the label connection). A
    #    digit in this group is the drift itself: the guard would compare one window's length
    #    against the constant while the query asks for another size.
    graded = sorted(s for _k, s in asks if s.startswith("{"))
    assert graded == sorted(
        [
            "{EVENT_WINDOW}",
            "{EVENT_WINDOW}",
            "{EVENT_WINDOW}",
            "{EVENT_WINDOW}",
            "{DISCOVERY_WINDOW}",
        ]
    ), asks
    # 2. The bare digits are an enumerated, reasoned residue -- not an unchecked remainder.
    #    `labels(first: 20)` is the last one: `_pr_fields` sorts a label SET, which has no
    #    chronology and no fullness test, so no guard can grade a different window than it asks for.
    #    (`contexts` left this group when `_truncated` started measuring it.)
    literal = sorted(s for _k, s in asks if not s.startswith("{"))
    assert literal == sorted(["20"]), (
        f"a new typed page size appeared, or one lost its reason: {literal}"
    )
    # 3. The rendered query, so the constant's VALUE is checked against GitHub's cap, not just its
    #    spelling: 101 would interpolate happily and still be rejected by the API.
    query = watch.query_text([PR], REPO, RULING_ISSUE, [LANE_OPS])
    assert f"comments(last: {watch.EVENT_WINDOW})" in query
    assert f"reviews(last: {watch.EVENT_WINDOW})" in query
    # The braces survive the f-string: `{{` must render one `{`, or the query is malformed and
    # GitHub rejects the whole poll -- a break the AST census cannot see (it reads source, not text).
    assert f"contexts(last: {watch.EVENT_WINDOW}) {{" in query
    # And the count that makes the window a CLAIM, sliced to THIS connection for the reason above:
    # `_truncated` reads wrapper["totalCount"], so an ask that drops it answers None -- which the
    # guard treats as truncation, degrading the line to "100 of ?" instead of failing. A field that
    # only degrades a message when deleted still needs a witness, or it will be dropped as unused.
    block = query[query.index("contexts(last:") :]
    assert "totalCount" in block[: block.index("nodes {")], (
        "the check window must ask its own total: without it a full window cannot say what it hid"
    )
    assert watch.EVENT_WINDOW <= 100, "GitHub caps a connection page at 100 nodes"
    assert watch.DISCOVERY_WINDOW <= 100


def test_explicit_pr_numbers_are_watched_whether_or_not_a_label_matches():
    """Ruling 193: the labels PLUS any PR numbers it is given."""
    state = {}
    runner = Run(
        envelope(
            [pr_node(9999)],
            ruling_ids=[1],
            ruling_bodies={1: "BINDING NOW: x"},
            found={"a0": discovery_node([])},
        )
    )
    watch.check(
        runner,
        state,
        repo=REPO,
        prs=[9999],
        ruling_issue=RULING_ISSUE,
        label_groups=[LANE_OPS],
    )
    assert "p9999: pullRequest(number: $p9999)" in runner.queries[0]
    assert state["watched"] == [9999], "an unmatched number stays watched"
    # ...and its events are reported, not just its number tracked.
    moved = envelope(
        [pr_node(9999, head="f" * 40)],
        ruling_ids=[1],
        ruling_bodies={1: "BINDING NOW: x"},
        found={"a0": discovery_node([])},
    )
    lines = watch.check(
        Run(moved),
        state,
        repo=REPO,
        prs=[9999],
        ruling_issue=RULING_ISSUE,
        label_groups=[LANE_OPS],
    )
    assert len(lines) == 1 and lines[0].startswith("#9999 "), lines


def test_a_pr_that_merged_before_its_first_field_read_is_still_reported():
    """A merge between discovery and the first field read must not vanish into the seed.

    Discovery gives a NUMBER; the fields are asked from the next poll on, and the poll that first
    reads them seeds them -- normally silently. But `states: [OPEN]` guarantees a discovered PR was
    open when it appeared, so if the first read finds MERGED, the merge happened under the watcher
    and IS news. Absent-vs-null is the distinction here: a not-asked alias is absent from the
    response, an inaccessible PR is an explicit null, and only the null stays silent.
    """
    state = {}
    first = Run(
        envelope(
            [],
            ruling_ids=[1],
            ruling_bodies={1: "BINDING NOW: x"},
            found={"a0": discovery_node([PR])},
        )
    )
    assert (
        watch.check(
            first,
            state,
            repo=REPO,
            prs=[],
            ruling_issue=RULING_ISSUE,
            label_groups=[LANE_OPS],
        )
        == []
    ), "seed"
    merged_early = Run(
        envelope(
            [pr_node(PR, state="MERGED")],
            ruling_ids=[1],
            ruling_bodies={1: "BINDING NOW: x"},
            found={"a0": discovery_node([])},
        )
    )
    lines = watch.check(
        merged_early,
        state,
        repo=REPO,
        prs=[],
        ruling_issue=RULING_ISSUE,
        label_groups=[LANE_OPS],
    )
    assert len(lines) == 1 and "merged" in lines[0].lower(), lines


def test_every_alias_is_a_child_of_the_repository_node():
    """Braces must BALANCE and every alias must sit INSIDE `repository`, by depth, not by luck.

    Found live, not in the fixture: the discovery loop closed its connection twice, which ended
    `repository` early and pushed every `p<n>` alias to the query root -- GitHub answered "Expected
    one of SCHEMA, SCALAR, TYPE, ENUM, INPUT, UNION, INTERFACE, actual: IDENTIFIER (\"p7175\")".
    No change test could see that: ``envelope`` builds the response from the same aliases
    independently of the query text, so a malformed query still yields a fixture the parser reads
    happily. Depth is the invariant the parser relies on, so depth is what is asserted.
    """
    query = watch.query_text([7175, 7176], REPO, RULING_ISSUE, [LANE_OPS, REVIEW_A])
    depth = 0
    for line in query.splitlines():
        stripped = line.strip()
        opens, closes = stripped.count("{"), stripped.count("}")
        assert depth + opens - closes >= 0, f"brace closes more than it opens: {stripped!r}"
        if stripped.startswith(("p71", "a0:", "a1:", "issue(number")):
            assert depth == 2, f"alias at depth {depth}, not inside repository: {stripped!r}"
        depth += opens - closes
    assert depth == 0, f"unbalanced query: depth {depth} at the end"


def test_a_pr_named_by_number_AND_matched_by_a_label_is_read_on_the_first_poll():
    """The overlap case, which the registration path can silently downgrade.

    A PR an agent passed with ``--pr`` that also carries its lane label is in BOTH sets on the very
    first poll: its fields were just read as ``p<n>`` AND its number came back from the discovery
    connection. Registering it as "newly discovered" then would overwrite the fields it already has
    with UNREAD -- and a watcher that forgets what it read reports nothing about its own PRs. The
    mutation battery found this case untested; the mutant that wipes the fields survived nothing
    until this test existed.
    """
    state = {}
    runner = Run(
        envelope(
            [pr_node(PR)],
            ruling_ids=[1],
            ruling_bodies={1: "BINDING NOW: x"},
            found={"a0": discovery_node([PR])},
        )
    )
    lines = watch.check(
        runner,
        state,
        repo=REPO,
        prs=[PR],
        ruling_issue=RULING_ISSUE,
        label_groups=[LANE_OPS],
    )
    assert lines == [], "the seed poll is silent whatever the number came from"
    assert watch._read(state["prs"][PR]), (
        "its fields survived registration -- not downgraded to UNREAD"
    )
    assert state["watched"] == [PR], "watched once, not twice"
    # and it still reports events, which is what a downgraded entry would break.
    moved = envelope(
        [pr_node(PR, head="9" * 40)],
        ruling_ids=[1],
        ruling_bodies={1: "BINDING NOW: x"},
        found={"a0": discovery_node([PR])},
    )
    lines = watch.check(
        Run(moved),
        state,
        repo=REPO,
        prs=[PR],
        ruling_issue=RULING_ISSUE,
        label_groups=[LANE_OPS],
    )
    assert len(lines) == 1 and lines[0].startswith(f"#{PR} "), lines


def test_the_no_change_line_counts_the_watched_set_not_the_launch_flags():
    """The headline of a silent lifetime must describe what actually sat here.

    An agent arms with `--lane ops --cell a` and NO `--pr`; discovery finds two PRs. Every other
    lifetime test passes explicit numbers, where the launch count and the watched count are equal
    and the two expressions are interchangeable -- the mutation battery found exactly that, and a
    line saying "no change across 0 watched PR(s)" would be true of the flags and false of the
    watch. Headline claims carry their n; this one has to carry the right n.
    """
    found = {"a0": discovery_node([7175, 7176])}
    same = envelope(
        [pr_node(7175), pr_node(7176)],
        ruling_ids=[1],
        ruling_bodies={1: "BINDING NOW: x"},
        found=found,
    )
    sim = Sim()
    rc, lines = watch.watch(
        Run(*([same] * 40)),
        {},
        sim.clock,
        sim.sleep,
        repo=REPO,
        prs=[],  # armed by label alone
        ruling_issue=RULING_ISSUE,
        label_groups=[LANE_OPS],
        interval=60,
        lifetime=600,
        max_errors=3,
    )
    assert rc == 0 and len(lines) == 1, lines
    assert lines[0].lower().startswith("no change"), lines
    assert "2 watched" in lines[0], f"the watched set, not the empty flag list: {lines[0]!r}"


def test_the_cli_builds_the_same_groups_the_ruling_names():
    """argv sits outside the runner seam, so the flag-to-group mapping is pinned directly."""
    argv = ["--lane", "ops", "--cell", "a", "--review-label", "review:ops-a", "--pr", "7175"]
    args = watch.parse_args(argv)
    assert args.prs == [7175]
    assert watch.label_groups(args.lane, args.cell, args.review_labels) == OPS_A


def test_a_repeated_pr_number_arms_one_watch_and_one_declaration():
    """`--pr 7175 --pr 7175` is a legal arm that used to produce a query the API always rejects.

    Two faces of the same bug, so both are pinned: the parsed list (dedup, first-occurrence order)
    and the QUERY TEXT, which declares ``$p<number>`` once per list entry -- a duplicate entry
    emits ``$p7175`` twice and every poll dies with ``variableNotUnique`` (measured live). Pinning
    only the list would survive a refactor that moved the dedup somewhere the query never passes
    through; the declaration census is the symptom's own shape. lane.md step 6 tells agents to
    pass repeated ``--pr`` flags, where one number can legitimately arrive twice.
    """
    args = watch.parse_args(["--pr", "7175", "--pr", "7175", "--pr", "7168", "--pr", "7175"])
    assert args.prs == [7175, 7168], "dedup keeps first-occurrence order"
    text = watch.query_text(args.prs, REPO, RULING_ISSUE)
    declared = re.findall(r"\$p\d+(?=[: ])", text.split("query(")[1].split(")")[0])
    assert sorted(declared) == ["$p7168", "$p7175"], "every $p declared EXACTLY once"


def test_the_cli_refuses_to_arm_with_nothing_to_watch():
    """No `--pr` and no discovering label is a watcher that watches nothing — refused at the CLI.

    This is the same blind spot as finding 4, one layer up: armed with no numbers and no label the
    watched set is empty forever, so `parse_args` errors out rather than backgrounding a silent
    poll. `parser.error` raises SystemExit(2), and an empty argv here is the whole hazard — the
    defaults (`--lane ""`, empty `--review-label`) are exactly what a mistyped arm produces.
    """
    with pytest.raises(SystemExit) as caught:
        watch.parse_args([])
    assert caught.value.code == 2
    # a label alone IS enough to watch (the idle-lane case finding 4 is about), so it must pass:
    assert watch.parse_args(["--lane", "ops"]).lane == "ops"


# ---------------------------------------------------------------------------- the watch loop


class Sim:
    """A clock and a sleep that move together, so the lifetime bound is a real simulation.

    ``sleep(s)`` records the wait AND advances the clock, so a test can hand the loop a bounded
    lifetime and see it end at the right moment rather than trusting a counted sleep list.
    """

    def __init__(self):
        self.now = NOW
        self.slept: list[int] = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += watch.timedelta(seconds=seconds)


def test_transient_error_does_not_end_the_watch():
    """One failed poll, then good data with a real change: the change is reported, not the error."""
    state = seed()
    moved = envelope(
        [pr_node(PR, head="b" * 40)], ruling_ids=[1], ruling_bodies={1: "BINDING NOW: x"}
    )
    runner = Run(RuntimeError("gh: connection reset"), moved)
    sim = Sim()
    rc, lines = watch.watch(
        runner,
        state,
        sim.clock,
        sim.sleep,
        repo=REPO,
        prs=[PR],
        ruling_issue=RULING_ISSUE,
        interval=60,
        lifetime=3600,
        max_errors=3,
    )
    assert rc == 0, "a transient error must not be fatal"
    assert lines and "head" in lines[0]
    # exactly one sleep: the failed poll slept, the next poll found the change and returned without
    # sleeping -- the watcher exits the moment it reports.
    assert sim.slept == [60], "the failed poll slept and the next poll was attempted"


def test_repeated_failures_exit_with_an_error_line():
    state = seed()
    runner = Run(*([RuntimeError("gh: 502 bad gateway")] * 3))
    sim = Sim()
    rc, lines = watch.watch(
        runner,
        state,
        sim.clock,
        sim.sleep,
        repo=REPO,
        prs=[PR],
        ruling_issue=RULING_ISSUE,
        interval=60,
        lifetime=3600,
        max_errors=3,
    )
    assert rc != 0, "repeated failures must exit non-zero: silence is not success"
    assert len(lines) == 1 and "error" in lines[0].lower()


def test_a_watch_that_never_read_a_window_cannot_print_the_all_clear():
    """A degraded lifetime (all polls fail, just under the fatal streak) is the error exit.

    The finding this pins: two polls fail (``max_errors=3`` so the streak is not yet fatal), the
    bound fires before a third can trip it, and the OLD code fell through to the calm
    ``no change in Ns`` headline -- an all-clear from a watcher that read zero windows. ``errors``
    resets to 0 on any success, so the calm path never saw the dead stretch. The witness is
    ``runner.calls == 2``: the bound is checked at the TOP of the loop, so with ``lifetime=120``
    and ``interval=60`` the watch attempts the polls at t=0 and t=60 (both scripted to fail) and
    reaches the bound before a third is attempted -- a script with a third response would sit
    unconsumed and the test would pin a shape that never happened.
    """
    runner = Run(
        RuntimeError("gh: 502 bad gateway"),
        RuntimeError("gh: 502 bad gateway"),
    )
    sim = Sim()
    rc, lines = watch.watch(
        runner,
        {},  # no prior state: the one clean poll would be the seed, and it never happens
        sim.clock,
        sim.sleep,
        repo=REPO,
        prs=[PR],
        ruling_issue=RULING_ISSUE,
        interval=60,
        lifetime=120,  # polls at t=0, t=60 (both fail), then t=120 hits the bound
        max_errors=3,
    )
    assert runner.calls == 2, "both polls in the budget ran and failed; the bound cut it off"
    assert rc == 2, f"a watch with 0 clean polls cannot certify 'no change': rc={rc} {lines}"
    assert len(lines) == 1 and "0 successful polls" in lines[0], lines
    assert "502" in lines[0], (
        f"the line must carry the last failure, not just the count: {lines[0]}"
    )


def test_a_lifetime_that_prevents_the_first_poll_is_the_error_exit():
    """A bound met before poll one reports an error, not a calm zero-window all-clear.

    ``lifetime <= 0`` reaches the bound on the loop's first pass, before any poll; the OLD code
    printed ``no change in 0s across 1 watched PR(s)`` with rc 0 -- an all-clear backed by zero
    API calls. The runner here scripts NOTHING, so a single attempted poll raises ``unscripted
    read``: ``calls == 0`` is the positive control proving the exit came from the never-polled
    guard and not from a runner that ran out. (The CLI now also refuses to arm this; this test
    pins the seam, which any non-CLI caller -- or a future default change -- reaches too.)
    """
    runner = Run()  # scripted empty: any poll raises, so a nonzero call count is caught here
    sim = Sim()
    rc, lines = watch.watch(
        runner,
        {},
        sim.clock,
        sim.sleep,
        repo=REPO,
        prs=[PR],
        ruling_issue=RULING_ISSUE,
        interval=60,
        lifetime=0,
        max_errors=3,
    )
    assert runner.calls == 0, "the whole point: not one poll was attempted"
    assert rc == 2, f"an all-clear with no window behind it must not be rc 0: {lines}"
    assert (
        len(lines) == 1 and "0 successful polls" in lines[0] and "first poll never ran" in lines[0]
    )


def test_a_watch_whose_only_clean_poll_was_the_seed_cannot_print_the_all_clear():
    """Round nine's MEDIUM 1: one successful read is not a comparison, and ``no change`` claims one.

    Round eight closed the zero-clean-poll watch; this is the neighbour it left open. With
    ``lifetime == interval`` the bound is met right after the seed, and the seed -- which reads a
    window, answers cleanly and reports NOTHING by design -- is the only clean poll. The old code
    counted it and printed the calm headline: reproduced at 3fd91e4c6 as
    ``no change in 60s across 1 watched PR(s)`` at rc 0 with ``diff_lines`` reached **zero** times,
    on a head that had in fact moved. So the arm that terminates soonest is the one that lies most.

    The witness is that the poll SUCCEEDED: ``runner.calls == 1`` and the scripted envelope was
    consumed, so the error line cannot be blamed on a failed read -- this is the shape round eight's
    ``clean_polls == 0`` guard could not see, and a mutant that reverts to that guard reddens exactly
    this test. The line names the successful-poll count too, because the distinction an agent acts on
    is "it read and did not look", not "it read nothing".
    """
    runner = Run(envelope([pr_node(PR)], ruling_ids=[1], ruling_bodies={1: "BINDING NOW: 45 live"}))
    sim = Sim()
    rc, lines = watch.watch(
        runner,
        {},
        sim.clock,
        sim.sleep,
        repo=REPO,
        prs=[PR],
        ruling_issue=RULING_ISSUE,
        interval=60,
        lifetime=60,  # seed at t=0, sleep, bound met at t=60: exactly one poll, and it was the seed
        max_errors=3,
    )
    assert runner.calls == 1, "one poll, scripted and successful -- no failure to blame"
    assert rc == 2, f"a watch that compared no window cannot certify 'no change': rc={rc} {lines}"
    assert len(lines) == 1, lines
    assert "compared" in lines[0], f"the line must name the missing comparison: {lines[0]}"
    assert "1 successful poll" in lines[0], f"and it must not miscount what it did: {lines[0]}"
    assert "no change" not in lines[0], lines


def test_a_resumed_watch_keeps_the_all_clear_on_its_first_comparing_poll():
    """The two-sided control: the guard refuses SEED-ONLY watches, not every single-poll watch.

    A one-sided test would be satisfied by a guard that refuses all short watches -- which is the
    shape a ``clean_polls >= 2`` bound takes, and it is wrong: a caller that arrives with a state
    that already seeded (a resumed watch) DOES compare on its very first poll, and its
    ``no change in 60s`` is an honest report about a window it looked at. This watch is identical
    to the one above except that its state comes from ``seed()``, so the pair pins the mechanism to
    the comparison and not to the poll count. ``watched == [PR]`` after the run is the witness that
    the all-clear here is the guard's correct answer rather than a pass-through.
    """
    state = seed()
    same = envelope([pr_node(PR)], ruling_ids=[1], ruling_bodies={1: "BINDING NOW: 45 live"})
    runner = Run(same)
    sim = Sim()
    rc, lines = watch.watch(
        runner,
        state,
        sim.clock,
        sim.sleep,
        repo=REPO,
        prs=[PR],
        ruling_issue=RULING_ISSUE,
        interval=60,
        lifetime=60,
        max_errors=3,
    )
    assert runner.calls == 1, "one poll, and that poll compared against the resumed state"
    assert rc == 0, f"a watch that compared a window keeps its all-clear: {lines}"
    assert len(lines) == 1 and lines[0].lower().startswith("no change"), lines
    assert state["watched"] == [PR], state["watched"]


def test_a_clean_watch_that_ended_on_failures_says_so():
    """The all-clear survives real comparisons, but the failure tail it ended on gets named.

    Seed at t=0, a comparing poll at t=60, a failure at t=120, the bound at t=180: the watch
    really did look, so the all-clear stands (rc 0) -- but the last poll never answered, and a bare
    "no change" would imply the opposite. The caveat rides the same two surfaces the
    truncated-window caveat rides, for the same reason: the headline is the only line that claims
    nothing happened.

    This test needed one more poll when the seed-only escape was closed, and that is worth stating
    rather than burying: as written it passed ``{}`` with a SINGLE clean poll, so the one poll it
    counted was the seed, and its docstring's claim that this "is a watch that really did read its
    windows" was false -- it is the same impersonation round nine's MEDIUM found in the watcher,
    sitting in the test that documented the all-clear's honesty. The fix is the extra poll, not a
    relaxed assertion.
    """
    runner = Run(
        envelope([pr_node(PR)], ruling_ids=[1], ruling_bodies={1: "BINDING NOW: 45 live"}),
        envelope([pr_node(PR)], ruling_ids=[1], ruling_bodies={1: "BINDING NOW: 45 live"}),
        RuntimeError("gh: 502 bad gateway"),
    )
    sim = Sim()
    rc, lines = watch.watch(
        runner,
        {},
        sim.clock,
        sim.sleep,
        repo=REPO,
        prs=[PR],
        ruling_issue=RULING_ISSUE,
        interval=60,
        lifetime=180,
        max_errors=3,
    )
    assert runner.calls == 3, "the seed, one comparing poll, then the failing one, then the bound"
    assert rc == 0, f"a watch that DID read a window keeps the all-clear: {lines}"
    assert lines[0].lower().startswith("no change"), lines
    assert len(lines) == 2, f"the all-clear must carry its tail caveat as its own line: {lines}"
    assert "failures" in lines[1] and "never read" in lines[1], lines


def test_the_cli_refuses_a_lifetime_that_could_never_poll():
    """``--lifetime 0`` / negative is a nonsense arm; ``parse_args`` fails it, not the watch.

    The file already fails a nonsense arm this way (``nothing to watch``), so a non-positive
    lifetime joins it rather than arming a zero-poll watch that prints a calm rc-0 line. Positive
    control at the bottom: a positive lifetime still parses, so the guard rejects the boundary and
    not all input.
    """
    for bad in ("0", "-1"):
        with pytest.raises(SystemExit):
            watch.parse_args(["--pr", "7175", "--lifetime", bad])
    assert watch.parse_args(["--pr", "7175", "--lifetime", "1"]).lifetime == 1.0


def test_the_cli_refuses_an_interval_that_could_never_poll():
    """``--interval 0`` / negative is refused at the arm. Round nine's MEDIUM 2.

    Two distinct harms, both measured here rather than inferred from the flag's name.
    ``interval == 0`` means no sleep between polls: the loop spins and hammers the owner token that
    ruling 193 limits to one shared budget -- the same reason the watcher uses one GraphQL query
    per poll instead of the 30/min search API. A negative value is worse than slow: the
    ``sleep(interval)`` at the bottom of ``watch`` sits OUTSIDE its ``try``/``except`` (deliberately
    -- a sleep failure is not a transient API error worth retrying), so ``time.sleep(-5)`` raises
    ``ValueError: sleep length must be non-negative``.

    Positive control at the bottom: a positive interval still parses, so the guard rejects the
    boundary and not all input. Same shape as ``test_the_cli_refuses_a_lifetime_that_could_never_poll``.
    """
    for bad in ("0", "-1"):
        with pytest.raises(SystemExit):
            watch.parse_args(["--pr", "7175", "--interval", bad])
    assert watch.parse_args(["--pr", "7175", "--interval", "1"]).interval == 1.0


def test_the_cli_defaults_are_the_ones_the_package_text_promises():
    """The package says "about every 60 s" and "repeated failures" end the watch; 3 is what
    `repeated` means here. Every ``watch()`` test passed ``interval``/``max_errors`` explicitly,
    so the shipped defaults could drift to any other value with nothing red -- a promise in the
    package text held only by prose. Pinned at the parse surface, which is where an arm without
    those flags actually reads them.
    """
    args = watch.parse_args(["--pr", "7175"])
    assert args.interval == 60.0, f"the package says 'about every 60 s': {args.interval}"
    assert args.max_errors == 3, f"'repeated failures' is 3 consecutive polls: {args.max_errors}"
    # The lifetime default is the one an agent that FORGETS --lifetime gets; it must terminate on
    # its own (that is the whole point of the bound) rather than run unseen forever.
    assert args.lifetime == 3600.0, args.lifetime


def test_a_guard_that_raises_routes_to_the_error_exit_and_not_to_a_calm_tick():
    """The ruling guard's raise must reach the error EXIT, not print nothing and exit 0.

    The fixture used to script EXACTLY `max_errors` responses, which made the test pass for a reason
    it never named: drop the `_check_ruling` call and the scripted runner simply runs out, and
    `watch`'s deliberately broad `except Exception` turns the runner's own "unscripted read"
    AssertionError into the same error line -- three more polls later, but the same rc and the same
    line. So the old test survived the mutant named after its own guard (measured: `1 passed` with
    `ruling-guard-never-runs` applied). Scripting MORE finite responses does not fix that, it only
    moves the exhaustion further out; the runner here answers forever, so exhaustion cannot happen at
    any point and the guard's raise is the only thing that can produce an error. With the guard
    removed every poll "succeeds", the loop runs its whole lifetime and prints "no change" -- the
    exact lie the guard exists to refuse. `test_a_null_ruling_issue_raises_instead_of_looking_calm`
    remains the guard's own pin at the `check()` seam; this one pins the ROUTING.
    """
    state = seed()
    deaf = envelope([pr_node(PR)], ruling_ids=None)
    polls: list[int] = []

    def deaf_runner(query: str, variables: dict) -> dict:
        polls.append(1)
        return deaf

    sim = Sim()
    rc, lines = watch.watch(
        deaf_runner,
        state,
        sim.clock,
        sim.sleep,
        repo=REPO,
        prs=[PR],
        ruling_issue=RULING_ISSUE,
        interval=60,
        lifetime=3600,
        max_errors=3,
    )
    assert rc != 0, "a channel that cannot see its rulings is not a calm tick"
    assert len(lines) == 1 and "error" in lines[0].lower()
    assert "ruling issue" in lines[0], f"the line must name the guard that raised: {lines}"
    assert len(polls) == 3, "the streak is fatal at max_errors, not after the lifetime"


def _busy(number=PR, *, returned=100, total=140, head="a" * 40):
    """A head whose check window came back FULL while the server counts more runs than it holds."""
    return envelope(
        [
            pr_node(
                number,
                head=head,
                checks=tuple((f"check-{i}", "SUCCESS", "COMPLETED") for i in range(returned)),
                check_total=total,
            )
        ],
        ruling_ids=[1],
        ruling_bodies={1: "BINDING NOW: x"},
    )


def test_a_full_check_window_qualifies_the_news_it_reports():
    """A `last:` window that came back full says so on the report it produces.

    Round six's second MEDIUM, measured by the reviewer at 79/100 on the head under review and by me
    at 31/31 on the next one -- the count tracks pushes, so a fixture can't wait for it. The harm is
    silent and it is an OMISSION: `_checks` maps name to conclusion and `diff_lines` iterates only
    the new side, so a run that aged out of the window reports neither a transition nor its absence.
    """
    state = {}
    runner = Run(_busy(), _busy(head="b" * 40))
    assert watch.check(runner, state, prs=[PR], ruling_issue=RULING_ISSUE) == []  # seed poll
    lines = watch.check(runner, state, prs=[PR], ruling_issue=RULING_ISSUE)
    assert f"#{PR} new head {'a' * 7} -> {'b' * 7}" in lines, lines
    assert f"#{PR} checks truncated: 100 of 140 watched" in lines, lines


def test_a_full_check_window_qualifies_the_all_clear_too():
    """The lifetime headline is where the caveat MUST land: it is the line read as an all-clear.

    The other half of the design, and the half a per-diff line alone misses: a head that is
    truncated and NEVER changes produces no diff, so the watch runs to its bound and prints "no
    change in 600s" -- which reads as "nothing moved", when what it means is "nothing moved in the
    windows I read". A truncated head that never changes still gets named, at expiry.
    """
    state = {}
    runner = Run(*([_busy()] * 200))
    sim = Sim()
    rc, lines = watch.watch(
        runner,
        state,
        sim.clock,
        sim.sleep,
        repo=REPO,
        prs=[PR],
        ruling_issue=RULING_ISSUE,
        interval=60,
        lifetime=600,
        max_errors=3,
    )
    assert rc == 0, lines
    assert lines[0].lower().startswith("no change"), lines
    assert lines[1:] == [f"#{PR} checks truncated: 100 of 140 watched"], lines


def test_a_short_check_window_claims_no_caveat():
    """The other side of the guard, so it cannot pass by always complaining.

    A window SHORTER than the cap returned every check that exists -- that is the proof behind the
    diff's precise words -- so a head with room to spare must produce no qualifier on either
    surface. Without this leg, `_truncated` returning a constant string would survive.
    """
    # Leg 1: a head with room to spare (one check, server agrees) must be silent even when it
    # changes -- otherwise a head at 1/100 would carry a caveat it has not earned.
    state = seed()
    lines = second(
        Run(envelope([pr_node(PR, head="b" * 40)], ruling_ids=[1], ruling_bodies={1: "x"})), state
    )
    assert any("new head" in line for line in lines), lines
    assert not any("truncated" in line for line in lines), lines
    # Leg 2: a FULL window whose totalCount EQUALS the node count holds everything. The cap is
    # reached but nothing is hidden, so complaining here is the false-alarm half of this bug -- the
    # count is 100 because there are exactly 100 checks, not because 40 were dropped.
    exact = _busy(returned=100, total=100)
    st2 = {}
    assert watch.check(Run(exact), st2, prs=[PR], ruling_issue=RULING_ISSUE) == []
    moved = _busy(returned=100, total=100, head="b" * 40)
    lines = second(Run(moved), st2)
    assert any("new head" in line for line in lines), lines
    assert not any("truncated" in line for line in lines), lines


def test_bounded_lifetime_exits_with_a_no_change_line():
    state = seed()
    same = envelope([pr_node(PR)], ruling_ids=[1], ruling_bodies={1: "BINDING NOW: 45 live"})
    runner = Run(*([same] * 200))
    sim = Sim()
    rc, lines = watch.watch(
        runner,
        state,
        sim.clock,
        sim.sleep,
        repo=REPO,
        prs=[PR],
        ruling_issue=RULING_ISSUE,
        interval=60,
        lifetime=600,
        max_errors=3,
    )
    assert rc == 0
    assert len(lines) == 1 and lines[0].lower().startswith("no change")
    assert sim.now >= NOW + watch.timedelta(seconds=600), "it ran to its lifetime bound"
    # 600s / 60s = 10 polls, one sleep each. This is the witness that the loop WAITED rather than
    # busy-spinning: a loop that polled without sleeping would reach the same clock position with
    # 200 calls and no sleeps, and would trip the owner token's rate limit that ruling 193 cites.
    assert runner.calls == 10, "one poll per interval for the whole lifetime"
    assert sim.slept == [60] * 10, "it slept the interval between polls, not spun"


def test_watch_reports_the_first_change_it_sees_and_stops():
    """The contract is ONE line naming PR+change, then exit -- the agent re-arms."""
    state = seed()
    same = envelope([pr_node(PR)], ruling_ids=[1], ruling_bodies={1: "BINDING NOW: 45 live"})
    moved = envelope(
        [pr_node(PR, head="c" * 40)], ruling_ids=[1], ruling_bodies={1: "BINDING NOW: x"}
    )
    runner = Run(*([same] * 2 + [moved] + [same] * 10))
    sim = Sim()
    rc, lines = watch.watch(
        runner,
        state,
        sim.clock,
        sim.sleep,
        repo=REPO,
        prs=[PR],
        ruling_issue=RULING_ISSUE,
        interval=60,
        lifetime=3600,
        max_errors=3,
    )
    assert rc == 0
    assert len(lines) == 1 and "head" in lines[0]
    assert runner.calls == 3, "it exits at the first change instead of polling on"


def test_the_watcher_docs_count_its_own_suite_and_campaign_rather_than_restating_them():
    """AGENTS.md's two numbers must EQUAL what the files contain, measured by AST.

    The prose said "37 tests" and "reverts 30 properties" while the files held 42 and 33 -- five
    tests and three mutants had landed without a re-stamp, and nothing could notice, because the
    numbers were typed rather than counted. This is the same shape as every other counting test in
    this package (a claim about a quantity read off the artifact rather than from memory), and it is
    why the guard parses instead of grepping: `grep -c "def test_"` counts the word, and a comment
    or a docstring mentioning `def test_` would satisfy it while the real count moved (the lesson
    this repo already learned about grep-based censuses).
    """
    tests = [
        node.name
        for node in ast.parse(HERE.read_text(encoding="utf-8")).body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]
    campaign = ast.parse(CAMPAIGN.read_text(encoding="utf-8"))
    mutants = next(
        node
        for node in campaign.body
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "MUTANTS"
    )
    prose = AGENTS_DOC.read_text(encoding="utf-8")
    suite = re.search(r"`scripts/test_pr_watch\.py` \((\d+) tests", prose)
    driver = re.search(r"reverts (\d+) properties", prose)
    assert suite and driver, f"AGENTS.md lost one of the two count sentences: {AGENTS_DOC}"
    assert int(suite.group(1)) == len(tests), (
        f"AGENTS.md says {suite.group(1)} tests; this file defines {len(tests)}"
    )
    assert int(driver.group(1)) == len(mutants.value.elts), (
        f"AGENTS.md says {driver.group(1)} properties; the campaign lists {len(mutants.value.elts)}"
    )


def test_lines_name_the_pr_number_in_every_change_class():
    for label, change in (
        ("head", pr_node(PR, head="d" * 40)),
        ("check", pr_node(PR, checks=(("X", "FAILURE", "COMPLETED"),))),
        ("review", pr_node(PR, reviews=("R1",))),
        ("comment", pr_node(PR, comments=(("C1", "u", "b"),))),
    ):
        state = seed()
        lines = second(
            Run(envelope([change], ruling_ids=[1], ruling_bodies={1: "BINDING NOW: x"})), state
        )
        assert lines and lines[0].startswith(f"#{PR} "), f"{label}: {lines}"


def test_gh_result_raises_on_nonzero_rc_and_on_graphql_errors():
    """``gh_result`` is the only place a transport failure can become visible, so both its raise
    branches are pinned directly -- a return-instead-of-raise mutant must die here, not in the
    injected seam. ``gh_args``/``parse_args`` are pure for the same reason (AGENTS.md: no network,
    no monkeypatching), so the subprocess stays out of it and only the result object is built.
    """
    import subprocess as _sp

    err = _sp.CompletedProcess(args=["gh"], returncode=1, stdout="", stderr="gh: Could not resolve")
    with pytest.raises(RuntimeError, match="Could not resolve"):
        watch.gh_result(err)
    # stderr empty -> stdout is the message, so a silent-stderr failure still names something.
    with pytest.raises(RuntimeError, match="boom"):
        watch.gh_result(_sp.CompletedProcess(args=["gh"], returncode=1, stdout="boom", stderr=""))
    errors = _sp.CompletedProcess(
        args=["gh"], returncode=0, stdout='{"errors": [{"message": "Field X missing"}]}', stderr=""
    )
    with pytest.raises(RuntimeError, match="Field X missing"):
        watch.gh_result(errors)
    ok = _sp.CompletedProcess(args=["gh"], returncode=0, stdout='{"data": {"rate": 1}}', stderr="")
    assert watch.gh_result(ok) == {"data": {"rate": 1}}
