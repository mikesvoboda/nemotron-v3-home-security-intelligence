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

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "uplevel" / "pr_watch.py"


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
        item = self.responses.pop(0) if self.responses else {}
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
    reviews=(),
    comments=(),
):
    """One PullRequest node in the shape the query parses: the fields the watcher diffs."""
    return {
        "number": number,
        "headRefOid": head,
        "state": state,
        "isDraft": False,
        "labels": {"nodes": [{"name": n} for n in labels]},
        # the rollup's checks live under contexts.nodes, NOT nodes -- verified against the live
        # schema (introspection: StatusCheckRollup.fields = commit/contexts/id/state). A fixture
        # using `nodes` here would match a wrong parser and both would fail on the first poll.
        "statusCheckRollup": {
            "contexts": {"nodes": [{"name": n, "conclusion": c, "status": s} for n, c, s in checks]}
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
    lines = watch.check(runner, state, NOW, repo=REPO, prs=list(prs), ruling_issue=RULING_ISSUE)
    assert lines == [], "the first poll seeds state; nothing is news yet"
    assert runner.calls == 1
    return state


def second(runner, state, now=NOW):
    return watch.check(runner, state, now, repo=REPO, prs=[PR], ruling_issue=RULING_ISSUE)


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
    watch.check(runner, state, NOW, repo=REPO, prs=[PR], ruling_issue=RULING_ISSUE)
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
            NOW,
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
        NOW,
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
        NOW,
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
        NOW,
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
        NOW,
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
            NOW,
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
        NOW,
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
        NOW,
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
        gone, state, NOW, repo=REPO, prs=[], ruling_issue=RULING_ISSUE, label_groups=[LANE_OPS]
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
        NOW,
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
    assert "totalCount" in query, "a full window must be distinguishable from an empty one"


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
            NOW,
            repo=REPO,
            prs=[PR],
            ruling_issue=RULING_ISSUE,
            label_groups=[LANE_OPS],
        )
    except RuntimeError as exc:
        assert "300" in str(exc) and "100" in str(exc), exc
    else:
        raise AssertionError("a truncated discovery window must raise, not report nothing")


def test_window_size_is_bounded_by_a_named_constant():
    """The `first:` a discovery connection asks for is the number the truncation guard compares to."""
    query = watch.query_text([PR], REPO, RULING_ISSUE, [LANE_OPS])
    assert f"first: {watch.DISCOVERY_WINDOW}" in query
    assert watch.DISCOVERY_WINDOW <= 100, "GitHub caps a connection page at 100 nodes"


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
        NOW,
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
        NOW,
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
            NOW,
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
        NOW,
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
        NOW,
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
        NOW,
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
