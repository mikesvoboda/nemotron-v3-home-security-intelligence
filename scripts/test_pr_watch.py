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


def envelope(prs, ruling_ids=None, ruling_bodies=None):
    """The single GraphQL response envelope, in the shape GitHub actually returns it.

    The aliases live INSIDE the one `repository` selection set (`data.repository.p7168`), because
    GraphQL has no top-level `pullRequest` field to alias. Getting this right is the point of the
    helper: a flat fixture would let a parser that misses the nesting pass every test and then
    find nothing in production.
    """
    repository = {f"p{p['number']}": p for p in prs}
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
