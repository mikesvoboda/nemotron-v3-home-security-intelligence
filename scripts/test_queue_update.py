#!/usr/bin/env python3
"""Tests for scripts/uplevel/queue_update.py (ruling 272), with no network.

Run explicitly; outside testpaths (like every scripts/test_*.py gate suite):

    uv run python -m pytest scripts/test_queue_update.py -q

One seam: ``queue_update.fire(run, repo, issue, token, run_url)`` takes the runner, so nothing
here patches a module global or reaches the network. The fake answers by command shape -- ``gh
api repos/…``, ``gh api graphql -f query=…``, ``git merge-base``/``git diff`` -- records every
call, and raises on a command nobody scripted, so a new read shows up as a failing test instead
of a live API call. Each test changes one answer of the shared green scenario, as
``test_coordinator_snapshot.py``'s do; the seven steps of ruling 272 item 3 each have a test,
plus the empty/missing queue line and the 409 conflict fallthrough.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "uplevel" / "queue_update.py"
SNAP = REPO_ROOT / "scripts" / "uplevel" / "coordinator_snapshot.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# queue_update imports its sibling by the bare module name (it puts its own directory on
# sys.path), so the sibling is registered under that name first.
_load("coordinator_snapshot", SNAP)
qu = _load("queue_update", SCRIPT)

REPO = "o/r"
ISSUE = 6854
GREEN = "success"
STATUS_ID = 6133025635
QUEUE_ID = 9999  # the PR comment the write path posts to
TIP = "f" * 40  # main's tip
LISTED = "a" * 40  # entry 111's coordinator-judged sha
HEAD = "b" * 40  # entry 111's current head
HEAD2 = "c" * 40  # entry 222's current head
GATE_HEAD = "e" * 40  # the head the fake answers check-runs for (entry 111's)
NEW_HEAD = "d" * 40  # the head after the update-branch merge
RUN_ID = 39370075787
GQL_ID = "PR_kgL Dresden".replace(" ", "")  # the GraphQL id, a shape not a secret


def diff_for(rev: str, content: str = "+line\n") -> str:
    """A plausible git diff for ``rev`` -- distinct index lines per rev, so the tests can
    tell a carry (same hash) from an author change (different hash) by construction."""
    return f"diff --git a/x.py b/x.py\nindex {rev[:8]}..{rev[:8]} 100644\n--- a/x.py\n+++ b/x.py\n@@ -1,1 +1,1 @@\n{content}"


class Fake:
    """Answers by command shape, records every call, raises on a command nobody scripted."""

    def __init__(self, **over):
        self.calls: list[list[str]] = []
        self.rules: dict[str, object] = {}
        self.comments = over.get("comments", [status_comment(over.get("queue", f"111@{HEAD[:9]}"))])
        self.prs = over.get("prs", {})
        self.gate_conclusion = over.get("gate_conclusion", GREEN)
        self.main_ci = over.get("main_ci", GREEN)
        self.files = over.get("files", ["backend/x.py"])
        self.diffs = over.get("diffs", {})  # rev -> diff text; default below = one carry
        self.update_status = over.get("update_status", 200)
        self.update_answer = over.get("update_answer", {"message": "Merged"})
        self.post_update_head = over.get("post_update_head", NEW_HEAD)
        self.update_pr = over.get("update_pr", 111)  # which PR's head moves on the update

    def fail(self, needle: str, message: str = "gh: HTTP 502 upstream") -> None:
        self.rules[needle] = RuntimeError(message)

    def __call__(self, cmd, stdin=""):
        cmd = [str(x) for x in cmd]
        self.calls.append(cmd)
        self.stdin_seen = stdin
        joined = " ".join(cmd)
        for needle, answer in self.rules.items():
            if needle in joined:
                if isinstance(answer, Exception):
                    raise answer
                return answer
        return self.default(cmd)

    def default(self, cmd):
        if cmd[:2] == ["git", "merge-base"]:
            return TIP  # every rev forks from today's main (the roll's merge-base)
        if cmd[:2] == ["git", "diff"]:
            # the rev lives in the range arg 'base..rev'; scan past the 'git','diff' argv
            # and the '--' separator, NOT from the whole command ('git' itself matches a
            # naive "not diff, not --" filter and dispatches nothing).
            args = [a for a in cmd[2:] if a != "--" and not a.startswith("--")]
            rev = args[0] if args else "x"
            for r in (r for r in self.diffs if r in rev):
                return self.diffs[r]
            return diff_for(HEAD)  # the shared default: a carry
        if cmd[:3] == ["gh", "api", "-X"]:
            return self.rest(cmd, self.stdin_seen)
        if cmd[:2] == ["gh", "api"]:
            return self.read(cmd)
        raise AssertionError(f"unexpected command {' '.join(cmd)}")

    def read(self, cmd):
        path = " ".join(cmd[2:])
        if path.startswith("graphql"):
            return self.graphql(cmd[-1].removeprefix("query="))
        if "issues/6854/comments" in path:
            return json.dumps(self.comments)
        if path.endswith("commits/main"):
            return json.dumps({"sha": TIP})
        if "actions/runs?" in path:
            if self.main_ci is None:
                return json.dumps({"workflow_runs": []})
            return json.dumps({"workflow_runs": [{"conclusion": self.main_ci}]})
        m = path.split("repos/o/r/pulls/")[-1]
        if m.endswith("/files?per_page=100"):
            return json.dumps([{"filename": f} for f in self.files])
        if m.isdigit():
            pr = self.prs.get(int(m), self.prs.get("default"))
            if pr is None:
                raise RuntimeError(f"gh: HTTP 404 for {m}")
            return json.dumps(pr)
        raise AssertionError(f"unscripted gh api read: {path}")

    def rest(self, cmd, stdin=""):
        # rest() sees the cmd once the -X form is matched in default(): METHOD at [3],
        # PATH at [4], the PUT body at the trailing stdin.
        method, path = cmd[3], cmd[4]
        if method == "PUT" and path.endswith("update-branch"):
            self.update_seen = json.loads(stdin)  # the body rode stdin, as it must
            self.calls[-1].append(f"stdin={stdin}")
            if self.update_status in (200, 202) and self.update_pr is not None:
                self.prs[self.update_pr]["head"]["sha"] = self.post_update_head
            return f"HTTP/2.0 {self.update_status}\n\n{json.dumps(self.update_answer)}"
        if method == "POST" and "issues/111/comments" in path:
            self.comment_body = cmd[-1].removeprefix("body=")
            return json.dumps({"id": QUEUE_ID, "html_url": "u"})
        raise AssertionError(f"unscripted gh api write: {method} {path}")

    def graphql(self, query):
        if "enablePullRequestAutoMerge" in query:
            self.armed = query
            return json.dumps(
                {"data": {"enablePullRequestAutoMerge": {"pullRequest": {"number": 111}}}}
            )
        if "disablePullRequestAutoMerge" in query:
            self.disarmed = query
            return json.dumps(
                {"data": {"disablePullRequestAutoMerge": {"pullRequest": {"number": 111}}}}
            )
        if "pullRequest(number:" in query:
            return json.dumps({"data": {"repository": {"pullRequest": {"id": GQL_ID}}}})
        raise AssertionError(f"unscripted graphql: {query[:60]}")


def status_comment(queue: str) -> dict:
    body = f"<!-- status:uplevel-coordinator -->\nuplevel · status\n<!-- queue: {queue} -->\n"
    return {"id": STATUS_ID, "body": body, "user": {"login": "mikesvoboda"}}


def pr(number, head, state="open", draft=False, base=TIP):
    return {
        "number": number,
        "state": state,
        "draft": draft,
        "head": {"sha": head},
        "base": {"sha": base},
    }


def check_runs(conclusion=GREEN):
    if conclusion is None:
        return {"check_runs": []}  # no gate check present at all
    return {
        "check_runs": [
            {"name": "CI Gate (Required Checks)", "conclusion": conclusion, "id": 1},
        ]
    }


def green(**over):
    """The shared green scenario: one queued entry 111, open, not behind, gate green,
    own-diff unchanged (a carry), and the fake's default runner is a fire through
    ``fire()``. Overrides change ONE fact each."""
    fake = Fake(**over)
    fake.prs = {
        111: pr(111, HEAD),
        222: pr(222, HEAD2),
    }
    return fake


def gate_answer(fake, conclusion):
    fake.rules["check-runs"] = json.dumps(check_runs(conclusion))


# -- step 1: reads ----------------------------------------------------------


def test_reads_the_queue_line_main_tip_and_ci():
    fake = green()
    plan = qu.fire(fake, REPO, ISSUE, None)
    assert plan.queue_entries == [qu.Entry(urgent=False, number=111, sha=HEAD[:9])]
    assert plan.main_tip == TIP
    assert plan.main_ci_conclusion == GREEN
    reads = ["issues/6854/comments", "commits/main", "actions/runs?branch=main"]
    for needle in reads:
        assert any(needle in " ".join(c) for c in fake.calls), needle
    assert plan.action == "no-op"  # green + not behind: the in-flight shape


def test_a_failed_queue_read_is_reported_not_swallowed():
    fake = green()
    fake.fail("issues/6854/comments", "gh: HTTP 502")
    plan = qu.fire(fake, REPO, ISSUE, None)
    assert plan.queue_entries == []
    assert plan.read_errors and "queue-line read" in plan.read_errors[0]
    assert plan.action == "none"  # an unread queue decides nothing


def test_main_ci_none_is_neither_red_nor_green():
    fake = green(main_ci=None)
    plan = qu.fire(fake, REPO, ISSUE, None)
    assert plan.main_ci_conclusion is None
    assert plan.action == "no-op"  # not "red", so the ! filter did not engage


# -- the queue-line grammar -------------------------------------------------


def test_empty_queue_line_reads_as_empty():
    assert qu.parse_queue_line("<!-- queue: -->") == []
    assert qu.parse_queue_line("no line here") == []
    assert qu.parse_queue_line("") == []


def test_parse_keeps_order_and_urgent_flag():
    line = "<!-- queue: !222@" + HEAD2[:9] + " 111@" + HEAD[:9] + " -->"
    got = qu.parse_queue_line(line)
    assert [(e.urgent, e.number, e.sha[:9]) for e in got] == [
        (True, 222, HEAD2[:9]),
        (False, 111, HEAD[:9]),
    ]


def test_malformed_token_skipped_rest_stands():
    line = "<!-- queue: junk 111@" + HEAD[:9] + " -->"
    got = qu.parse_queue_line(line)
    assert [e.number for e in got] == [111]


# -- step 2: in-flight no-op ------------------------------------------------


def test_not_behind_is_a_noop_even_with_a_queue():
    fake = green()  # pr base == TIP: the PR is current
    plan = qu.fire(fake, REPO, ISSUE, None)
    assert plan.action == "no-op"
    assert not any("PUT" in " ".join(c) for c in fake.calls), "wrote on a current PR"


def test_behind_entry_gates_the_update():
    fake = green()
    fake.prs[111] = pr(111, HEAD, base="0" * 40)  # behind: base != main tip
    gate_answer(fake, GREEN)
    plan = qu.fire(fake, REPO, ISSUE, None)
    assert plan.action == "update"
    assert plan.acted_entry == 111


# -- step 3: red main acts only on ! entries --------------------------------


def test_red_main_skips_a_plain_entry():
    fake = green(main_ci="failure")
    fake.prs[111] = pr(111, HEAD, base="0" * 40)  # behind and eligible otherwise
    gate_answer(fake, GREEN)
    plan = qu.fire(fake, REPO, ISSUE, None)
    assert plan.action == "no-op"
    assert "red main" in plan.action_note
    assert not any("PUT" in " ".join(c) for c in fake.calls)


def test_red_main_acts_on_an_urgent_entry():
    queue = f"!111@{HEAD[:9]}"
    fake = green(queue=queue, main_ci="failure")
    fake.prs[111] = pr(111, HEAD, base="0" * 40)
    gate_answer(fake, GREEN)
    plan = qu.fire(fake, REPO, ISSUE, None)
    assert plan.action == "update"
    assert plan.acted_entry == 111


# -- step 4: skips merged/closed/draft and hash-changed ---------------------


def test_merged_and_closed_and_draft_entries_skip():
    for state, draft in (("merged", False), ("closed", False), ("open", True)):
        fake = green()
        fake.prs[111] = pr(111, HEAD, state=state, draft=draft, base="0" * 40)
        gate_answer(fake, GREEN)
        plan = qu.fire(fake, REPO, ISSUE, None)
        assert plan.action == "no-op", (state, draft)
        assert not any("PUT" in " ".join(c) for c in fake.calls)


def test_own_diff_changed_drops_the_entry():
    fake = green()
    fake.prs[111] = pr(111, HEAD, base="0" * 40)
    gate_answer(fake, GREEN)
    fake.diffs = {LISTED: diff_for(LISTED), HEAD: diff_for(HEAD, "+changed\n")}
    plan = qu.fire(fake, REPO, ISSUE, None)
    assert plan.action == "no-op"  # the author commit dropped the entry
    assert not any("PUT" in " ".join(c) for c in fake.calls)


def test_own_diff_carry_updates():
    fake = green()
    fake.prs[111] = pr(111, HEAD, base="0" * 40)
    gate_answer(fake, GREEN)
    fake.diffs = {LISTED: diff_for(LISTED), HEAD: diff_for(HEAD)}  # distinct index lines,
    # but ur106_diff_hash drops index lines and blanks hunk headers, so both hash equal:
    # this asserts the FILTER, not the sha coincidence.
    assert qu.snap.ur106_diff_hash(diff_for(LISTED)) == qu.snap.ur106_diff_hash(diff_for(HEAD))
    plan = qu.fire(fake, REPO, ISSUE, None)
    assert plan.action == "update"


def test_a_failed_read_skips_instead_of_deciding():
    fake = green()
    fake.prs[111] = pr(111, HEAD, base="0" * 40)
    fake.fail("pulls/111", "gh: HTTP 502")  # the PR read itself fails
    plan = qu.fire(fake, REPO, ISSUE, None)
    assert plan.action == "no-op"
    assert any("pr read" in e for e in plan.entries[0].errors)


def test_gate_failed_entry_skips():
    fake = green()
    fake.prs[111] = pr(111, HEAD, base="0" * 40)
    gate_answer(fake, "failure")
    plan = qu.fire(fake, REPO, ISSUE, None)
    assert plan.action == "no-op"
    assert not any("PUT" in " ".join(c) for c in fake.calls)


def test_gate_in_flight_is_not_a_failure():
    fake = green()
    fake.prs[111] = pr(111, HEAD, base="0" * 40)
    gate_answer(fake, None)  # no gate check present: not a failure
    plan = qu.fire(fake, REPO, ISSUE, None)
    assert plan.action == "update"


# -- step 5: the update + arm + conflict ------------------------------------


def test_update_calls_update_branch_with_expected_head_and_arms():
    fake = green()
    fake.prs[111] = pr(111, HEAD, base="0" * 40)
    gate_answer(fake, GREEN)
    plan = qu.fire(fake, REPO, ISSUE, "tok-1")
    assert plan.action == "update"
    sent = (
        json.loads(fake.update_seen["expected_head_sha"])
        if isinstance(fake.update_seen, str)
        else fake.update_seen
    )
    assert sent["expected_head_sha"] == HEAD
    assert sent["update_method"] == "merge"
    assert any("update-branch" in " ".join(c) for c in fake.calls)
    assert getattr(fake, "armed", None) and "enablePullRequestAutoMerge" in fake.armed
    assert "MERGE" in fake.armed
    assert getattr(fake, "comment_body", None)  # step 7's comment went out


def test_conflict_409_falls_through_to_the_next_entry():
    queue = f"111@{HEAD[:9]} 222@{HEAD2[:9]}"
    fake = green(queue=queue)
    fake.prs[111] = pr(111, HEAD, base="0" * 40)
    fake.prs[222] = pr(222, HEAD2, base="0" * 40)
    gate_answer(fake, GREEN)  # both entries' gate reads pass; merge-bases all fork from main
    fake.update_status = 409
    fake.update_answer = {"message": "merge conflict"}
    plan = qu.fire(fake, REPO, ISSUE, "tok-1")
    puts_dbg = [" ".join(c) for c in fake.calls if "update-branch" in " ".join(c)]
    assert plan.action == "no-op", (plan.action, plan.action_note)  # fire stopped: both 409ed
    # the fallthrough DID reach entry 222 in the SAME fire (two update-branch PUTs, one fire):
    assert len(puts_dbg) == 2, puts_dbg
    assert plan.acted_entry in (None, 222)


def test_conflict_then_second_entry_updates():
    queue = f"111@{HEAD[:9]} 222@{HEAD2[:9]}"
    fake = green(queue=queue)
    fake.prs[111] = pr(111, HEAD, base="0" * 40)
    fake.prs[222] = pr(222, HEAD2, base="0" * 40)
    gate_answer(fake, GREEN)
    # the fake's rest() answers every PUT the same, so script a one-shot rule: the first
    # update-branch conflicts, the second (entry 222's) succeeds.
    first = {"done": False}

    class Once:
        def __init__(self, inner):
            self.inner = inner
            self.seen: list[str] = []

        def __call__(self, cmd, stdin=""):  # production calls run(cmd, stdin) -- even for reads
            if (
                cmd[:3] == ["gh", "api", "-X"]
                and "update-branch" in " ".join(cmd)
                and not first["done"]
            ):
                first["done"] = True
                self.seen.append(" ".join(cmd))  # the intercepted 409 is a PUT too
                return 'HTTP/2.0 409\n\n{"message": "conflict"}'
            out = self.inner(cmd, stdin)  # delegate everything, so the fake records it
            if cmd[:3] == ["gh", "api", "-X"] and "update-branch" in " ".join(cmd):
                self.seen.append(" ".join(cmd))
            return out

    once = Once(fake)
    fake.update_status = 200
    plan = qu.fire(once, REPO, ISSUE, "tok-1")
    assert plan.action == "update"
    assert plan.acted_entry == 222
    # Once.seen counts every update-branch PUT regardless of who answered it: the first
    # (entry 111, the 409) and the second (entry 222, success) -- one fire, both visible.
    assert len(once.seen) == 2, once.seen
    assert "111" in once.seen[0] and "222" in once.seen[1]


def test_update_failure_stops_the_fire_and_reports():
    fake = green()
    fake.prs[111] = pr(111, HEAD, base="0" * 40)
    gate_answer(fake, GREEN)
    fake.update_status = 500
    fake.update_answer = {"message": "boom"}
    plan = qu.fire(fake, REPO, ISSUE, "tok-1")
    assert plan.action == "update"  # the decision stands; the note says what failed
    assert "answered 500" in plan.action_note
    assert not getattr(fake, "armed", None), "armed after a failed update"


def test_no_token_writes_nothing():
    fake = green()
    fake.prs[111] = pr(111, HEAD, base="0" * 40)
    gate_answer(fake, GREEN)
    plan = qu.fire(fake, REPO, ISSUE, None)
    assert plan.action == "update"
    assert "no token" in plan.action_note
    assert not any("update-branch" in " ".join(c) for c in fake.calls)


def test_write_token_header_rides_exactly_the_write_calls():
    # Ruling 272 item 3 bounds the secret to the update-branch PUT and the auto-merge
    # arm/disable mutation: each carries `-H "Authorization: token <QUEUE_UPDATE_TOKEN>"`,
    # and NO read (or the step-7 comment POST, which rides the job token) carries one.
    fake = green()
    fake.prs[111] = pr(111, HEAD, base="0" * 40)
    gate_answer(fake, GREEN)
    plan = qu.fire(fake, REPO, ISSUE, "tok-1")
    assert plan.action == "update"

    def with_header(cmd):
        return any(a.startswith("Authorization: token ") for a in cmd)

    puts = [c for c in fake.calls if "update-branch" in " ".join(c)]
    assert len(puts) == 1 and with_header(puts[0])
    # the disable mutation only fires on the carry:no path, so this fire covers the arm
    # and the PUT; test_disarm_mutation_also_rides_the_write_header covers the disarm.
    arms = [c for c in fake.calls if any("enablePullRequestAutoMerge" in a for a in c)]
    assert len(arms) == 1 and with_header(arms[0])
    # the ONLY header-carrying calls are the PUT and the mutation -- every read, the
    # _pr_id graphql read, and the step-7 comment POST ride the job token instead.
    headered = [c for c in fake.calls if with_header(c)]
    assert len(headered) == 2, [" ".join(c)[:80] for c in headered]
    others = [c for c in fake.calls if not with_header(c)]
    assert any("issues/111/comments" in " ".join(c) for c in others), "comment POST misrouted"
    assert any("pullRequest(number:" in " ".join(c) for c in others), "_pr_id read misrouted"


def test_disarm_mutation_also_rides_the_write_header():
    # the carry:no fire: the re-hash disarms auto-merge, and that mutation carries the
    # write token's header too.
    fake = green()
    fake.prs[111] = pr(111, HEAD, base="0" * 40)
    fake.diffs = {
        HEAD: diff_for(HEAD),
        NEW_HEAD: diff_for(NEW_HEAD, "+author\n"),
        LISTED: diff_for(LISTED),
    }
    gate_answer(fake, GREEN)
    plan = qu.fire(fake, REPO, ISSUE, "tok-1")
    assert plan.action == "update" and "carry: no" in plan.action_note
    disarms = [c for c in fake.calls if any("disablePullRequestAutoMerge" in a for a in c)]
    assert len(disarms) == 1
    assert any(a.startswith("Authorization: token tok-1") for a in disarms[0])


# -- step 6: the re-hash across the update ----------------------------------


def test_carry_no_disarms_auto_merge():
    fake = green()
    fake.prs[111] = pr(111, HEAD, base="0" * 40)
    gate_answer(fake, GREEN)
    # at the NEW head the own diff changed: the update merge cannot have done that, an
    # author commit raced the fire, so step 6 disarms and leaves the PR to the coordinator.
    fake.diffs = {
        HEAD: diff_for(HEAD),
        NEW_HEAD: diff_for(NEW_HEAD, "+author\n"),
        LISTED: diff_for(LISTED),
    }
    plan = qu.fire(fake, REPO, ISSUE, "tok-1")
    assert getattr(fake, "disarmed", None), "auto-merge stayed armed on carry: no"
    assert "disablePullRequestAutoMerge" in fake.disarmed
    assert "carry: no" in plan.action_note
    assert not getattr(fake, "comment_body", None), "step 7's comment is for a carry"


def test_carry_yes_comments_with_both_hashes():
    fake = green()
    fake.prs[111] = pr(111, HEAD, base="0" * 40)
    gate_answer(fake, GREEN)
    plan = qu.fire(fake, REPO, ISSUE, "tok-1", run_url="https://example/run")
    body = fake.comment_body
    assert "Queue update (ruling 272)" in body
    assert HEAD[:9] in body and NEW_HEAD[:9] in body
    assert TIP[:9] in body
    assert "carry: yes" in body
    assert "https://example/run" in body


# -- step 7's other half: the summary every fire -----------------------------


def test_summary_written_even_when_doing_nothing():
    fake = green()  # current PR: a no-op fire
    plan = qu.fire(fake, REPO, ISSUE, None)
    out = qu.render_summary(plan)
    assert "Queue update (ruling 272)" in out
    assert "action: no-op" in out
    assert f"- queue: 111@{HEAD[:9]}" in out


def test_summary_caps_itself():
    fake = green()
    plan = qu.fire(fake, REPO, ISSUE, None)
    # read_errors render as one joined line, so the cap must come from per-line content:
    # 200 queued entries make 200 table rows, far past SUMMARY_LINES.
    plan.queue_entries = [qu.Entry(urgent=False, number=n, sha="a" * 9) for n in range(1, 201)]
    plan.entries = [qu.EntryState(entry=e, state="open", behind=False, gate_failed=False, head=HEAD) for e in plan.queue_entries]  # fmt: skip
    out = qu.render_summary(plan)
    assert out.count("\n") <= qu.SUMMARY_LINES + 2
    assert "capped" in out


def test_summary_reports_read_errors():
    fake = green()
    fake.fail("actions/runs?", "gh: HTTP 502")
    plan = qu.fire(fake, REPO, ISSUE, None)
    out = qu.render_summary(plan)
    assert "read errors" in out


# -- the CLI ----------------------------------------------------------------


def test_dry_run_prints_and_writes_nothing(capsys):
    fake = green()
    fake.prs[111] = pr(111, HEAD, base="0" * 40)
    gate_answer(fake, GREEN)
    rc = qu.main(["--repo", REPO, "--dry-run"], run=fake)
    assert rc == 0
    out = capsys.readouterr().out
    assert "action: update" in out
    assert "dry run: nothing written" in out
    assert not any("update-branch" in " ".join(c) for c in fake.calls)


def test_main_zero_exit_on_a_quiet_noop(capsys):
    fake = green()
    rc = qu.main(["--repo", REPO], run=fake)
    assert rc == 0
    assert "action: no-op" in capsys.readouterr().out
