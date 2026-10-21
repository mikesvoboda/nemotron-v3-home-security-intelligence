#!/usr/bin/env python3
"""Tests for scripts/uplevel/queue_update.py (ruling 272), with no network.

Run explicitly; outside testpaths (like every scripts/test_*.py gate suite):

    uv run python -m pytest scripts/test_queue_update.py -q

One seam: ``queue_update.fire(run, repo, issue, token, run_url)`` takes the runner, so nothing
here patches a module global or reaches the network. The fake answers by command shape -- ``gh
api repos/…``, ``gh api graphql -f query=…``, ``git fetch``/``git diff`` -- records every
call, and raises on a command nobody scripted, so a new read shows up as a failing test instead
of a live API call. Each test changes one answer of the shared green scenario, as
``test_coordinator_snapshot.py``'s do; the seven steps of ruling 272 item 3 each have a test,
plus the empty/missing queue line and the 409 conflict fallthrough.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

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
# r5's finding tags, cited in the test names' parentheticals so the suite self-documents
# which blocking finding each pin belongs to.
R5_B1_B3 = "r5 B1+B3: no merge-base call, sha-only fetch/diff args"
R5_B2 = "r5 B2: a timeout's argv (the token) never reaches the rendered error"


def diff_for(rev: str, content: str = "+line\n") -> str:
    """A plausible git diff for ``rev`` -- distinct index lines per rev, so the tests can
    tell a carry (same hash) from an author change (different hash) by construction."""
    return f"diff --git a/x.py b/x.py\nindex {rev[:8]}..{rev[:8]} 100644\n--- a/x.py\n+++ b/x.py\n@@ -1,1 +1,1 @@\n{content}"


class Fake:
    """Answers by command shape, records every call, raises on a command nobody scripted.

    The fake models gh's REAL write contract (N10): an HTTP >= 400 answer exits 1 with the
    `--include` status line on stdout -- so the fake RAISES a stdout-carrying error there,
    exactly what `real_run` does in production. Status 0 means the answer arrived with NO
    status line at all (a transport death): empty stdout, no raise... which the fake
    returns as empty output. A fake whose HTTP >= 400 answers arrived as plain returns
    would pass tests while production read every conflict as status 0 -- the drift N10
    caught.
    """

    def __init__(self, **over):
        self.calls: list[list[str]] = []
        self.rules: dict[str, object] = {}
        self.comments = over.get("comments", [status_comment(over.get("queue", f"111@{HEAD[:9]}"))])
        self.prs = over.get("prs", {})
        self.gate_conclusion = over.get("gate_conclusion", GREEN)
        self.main_ci = over.get("main_ci", GREEN)
        # r288 red-first: the conclusion a DIFFERENT workflow's runs list answers with.
        # The bug shipped this green answer into the red-main decision; the fix reads the
        # CI workflow's own runs instead. Tests drive it to stage the misread.
        self.other_runs_conclusion = over.get("other_runs_conclusion")
        self.files = over.get("files", ["backend/x.py"])
        self.diffs = over.get("diffs", {})  # rev -> diff text; default below = one carry
        # ruling 278: the subset carry reads three-dot compares beyond the hash path's
        # merge-base read -- the chain (``compare/<listed>...<head>`` answers commits[]) and
        # each merge parent's place on main (``compare/<p2>...<tip>`` answers status).
        # Scripted per (left, right) sha pair; anything unscripted answers the hash path's
        # default merge-base shape, which reads as an unknown on-main and no chain -- the
        # conservative answer a failed read must produce.
        self.compares = over.get("compares", {})
        self.update_status = over.get("update_status", 200)
        self.update_answer = over.get("update_answer", {"message": "Merged"})
        self.post_update_head = over.get("post_update_head", NEW_HEAD)
        self.update_pr = over.get("update_pr", 111)  # which PR's head moves on the update
        # n10: where the comments list splits across the two paginated page values.
        # None = everything on page 1 (the default shape most tests want); an index
        # actually exercises the later-page read.
        self.page_split = over.get("page_split")

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
        if cmd[:2] == ["git", "fetch"]:
            # real git exits 128 on a ref arg that is not an object name; a newline riding
            # the sha (the B1 class: unstripped stdout feeding a later argument) would land
            # here -- the fake refuses it loudly instead of fetching what git could not.
            revs = cmd[cmd.index("origin") + 1 :]
            for r in revs:
                if not re.fullmatch(r"[0-9a-f]{40}", r):
                    raise AssertionError(f"git fetch got a non-sha ref arg: {r!r} (B1)")
            return ""  # a depth-1 rev fetch succeeds silently
        if cmd[:2] == ["git", "diff"]:
            # the rev lives in the range arg 'base..rev'; scan past the 'git','diff' argv
            # and the '--' separator, NOT from the whole command ('git' itself matches a
            # naive "not diff, not --" filter and dispatches nothing).
            args = [a for a in cmd[2:] if a != "--" and not a.startswith("--")]
            rng = args[0] if args else "x"
            # same B1 class, at the range arg: a malformed base..rev is a git 128, not a diff
            if not re.fullmatch(r"[0-9a-f]{40}\.\.[0-9a-f]{40}", rng):
                raise AssertionError(f"git diff got a non-sha range arg: {rng!r} (B1)")
            for r in (r for r in self.diffs if r in rng):
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
            # the paginated contract: gh --paginate streams one JSON value per page. The
            # fake answers in exactly that shape (one array per page), and REQUIRES the
            # --paginate flag -- a single-page read regresses N1 and fails here, loud.
            if "--paginate" not in cmd:
                raise AssertionError("comments read without --paginate (N1 regression)")
            # two page values; page_split moves the boundary (n10: None = all on page 1)
            cut = len(self.comments) if self.page_split is None else self.page_split
            return json.dumps(self.comments[:cut]) + json.dumps(self.comments[cut:])
        if path.endswith("commits/main"):
            return json.dumps({"sha": TIP})
        if "actions/workflows/ci.yml/runs?" in path:
            # r288: the CI workflow's OWN runs — the path _main_ci_conclusion reads. The
            # fake answers one run, its conclusion from main_ci, so a red main (and the
            # !-filter) stay testable through the real path shape.
            if self.main_ci is None:
                return json.dumps({"workflow_runs": []})
            return json.dumps({"workflow_runs": [{"conclusion": self.main_ci}]})
        if "actions/runs?" in path:
            # Any OTHER runs path is a different workflow's runs list (Linear CI Status
            # Sync etc.). r288's bug read this endpoint with `workflow=CI` -- REST ignores
            # that filter, so the query returned the newest run of ANY workflow and the
            # red-main guard never fired. The fake now models that harm: it answers a
            # GREEN run (the misleading shape the bug saw) unless a test scripts a
            # different answer via rules, so the red-first test can pin "the green answer
            # arrives and is IGNORED".
            if self.main_ci is None:
                return json.dumps({"workflow_runs": []})
            return json.dumps(
                {"workflow_runs": [{"conclusion": self.other_runs_conclusion or "success"}]}
            )
        m = path.split("repos/o/r/pulls/")[-1]
        if m.endswith("/files?per_page=100"):
            return json.dumps([{"filename": f} for f in self.files])
        msha = re.search(r"/commits/([0-9a-f]+)$", path)
        if msha:
            # the listed sha rides the queue line as a 9-char prefix, so _hash_at expands it
            # to a full sha before the fetch (git cannot fetch a short sha). The fake
            # resolves any known constant's prefix, and refuses an unknown one the way the
            # API answers an ambiguous/missing short sha -- an error, not a guess.
            # (Anchored at $ so the gate read `commits/<head>/check-runs` does NOT land
            # here; that read keeps its own rules-scripted answer.)
            short = msha.group(1)
            for full in (TIP, LISTED, HEAD, HEAD2, NEW_HEAD, GATE_HEAD):
                if full.startswith(short):
                    return json.dumps({"sha": full})
            raise RuntimeError(f"gh: HTTP 422 ambiguous short sha {short}")
        if "/compare/" in path:
            # the own-diff hash's merge-base read (r5 B3): the server-side three-dot compare
            # names each rev's merge-base with the root, replacing the un-runnable
            # depth-1 `git merge-base`. The default says every rev forks from today's main
            # (TIP), the shape every carry scenario needs; a test scripts an override via
            # fail()/rules when it wants a different base.
            m = re.search(r"/compare/([0-9a-f]+)\.\.\.([0-9a-f]+)$", path)
            if m and (m.group(1), m.group(2)) in self.compares:
                return json.dumps(self.compares[(m.group(1), m.group(2))])
            return json.dumps({"merge_base_commit": {"sha": TIP}})
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
            # gh's real contract, modeled (N10): the status line is stdout (--include) even
            # on the exit-1 statuses -- the fake RAISES with stdout carried, exactly what
            # real_run does; status 0 means no status line at all (transport death), which
            # arrives as plain empty output.
            if self.update_status == 0:
                return ""
            out = f"HTTP/2.0 {self.update_status}\n\n{json.dumps(self.update_answer)}"
            if self.update_status in (200, 202):
                return out
            raise qu._GhRestError(f"gh api exited 1 ({self.update_status})", stdout=out)
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


@pytest.fixture
def r288_red_main():
    """The live r288 failure, staged: main's CI workflow reports failure while the
    any-workflow runs endpoint (the buggy query's real answer) reports a green plumbing
    run. Every assertion about which read decides follows from this one stage."""
    fake = green(main_ci="failure")
    fake.other_runs_conclusion = "success"
    return fake


# -- step 1: reads ----------------------------------------------------------


def test_reads_the_queue_line_main_tip_and_ci():
    fake = green()
    plan = qu.fire(fake, REPO, ISSUE, None)
    assert plan.queue_entries == [qu.Entry(urgent=False, number=111, sha=HEAD[:9])]
    assert plan.main_tip == TIP
    assert plan.main_ci_conclusion == GREEN
    reads = [
        "issues/6854/comments",
        "commits/main",
        # r288: the CI workflow's own runs, not the unscoped listing (REST has no
        # workflow filter there -- the unscoped query returned ANY workflow's newest run).
        "actions/workflows/ci.yml/runs?branch=main",
    ]
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


def test_status_comment_found_on_a_later_page():
    # N1: the status comment the coordinator edits in place slides deeper as #6854 grows
    # (page 5 of 9 live). The paginated read must find it wherever it sits: the fake
    # answers two page values with the status comment only on the SECOND (n10: the
    # boundary is real -- nothing before it can satisfy the marker scan).
    late = status_comment(f"111@{HEAD[:9]}")
    fake = green(comments=[{"id": 1, "body": "early chatter"}, late], page_split=1)
    plan = qu.fire(fake, REPO, ISSUE, None)
    assert [e.number for e in plan.queue_entries] == [111]
    assert plan.action == "no-op"  # green + current: read found, decision made


def test_a_missing_status_comment_is_a_fire_level_noop_not_an_error():
    # n8, at fire level: a comments list with NO marker-leading comment is a coordinator
    # who has not posted one yet -- an empty queue, not a failed read. (The parse-level
    # no-line shape is test_empty_queue_line_reads_as_empty.)
    fake = green(comments=[{"id": 1, "body": "just chatter"}, {"id": 2, "body": ""}])
    plan = qu.fire(fake, REPO, ISSUE, None)
    assert plan.queue_entries == []
    assert plan.read_errors == []  # the read SUCCEEDED; the queue is empty
    assert plan.action == "none"


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


def test_red_main_reads_the_ci_workflows_own_runs_not_any_workflows_newest(r288_red_main):
    # r288 red-first: `actions/runs?branch=main&workflow=CI` has NO workflow filter in
    # REST -- the query returned the newest completed run of ANY workflow, so on a red
    # main whose newest run is a green plumbing job (Linear CI Status Sync), the plan read
    # "success" and the !-filter never engaged. The fake stages exactly that live shape:
    # the CI workflow's OWN runs say failure (main_ci), while the any-workflow endpoint
    # answers a green run. The fix reads the workflow-scoped path ONLY -- the green
    # answer is never consulted, which is why the unscoped path shows up in NO recorded
    # call (a call-list pin, not a served-but-ignored claim).
    fake = r288_red_main
    assert fake.main_ci == "failure"  # the CI workflow's own runs: red
    assert fake.other_runs_conclusion == "success"  # a plumbing workflow: green
    plan = qu.fire(fake, REPO, ISSUE, None)
    assert plan.main_ci_conclusion == "failure"  # the red, not the plumbing green
    # the decision read the workflow-scoped path...
    ci_read = [c for c in fake.calls if any("workflows/ci.yml/runs" in x for x in c)]
    assert ci_read, "the CI workflow's own runs were never read"
    # ...and NEVER the unscoped listing whose answer here is green: if it had, the red
    # decision could not be trusted to have been read from the right place.
    unscoped = [c for c in fake.calls if "actions/runs?" in " ".join(c)]
    assert not unscoped, f"the unscoped runs listing was read: {unscoped}"
    assert "red main" in plan.action_note
    # and the decision: a plain (non-!) entry behind with a green gate freezes anyway
    assert plan.action == "no-op"
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


def _r278_chain(author=0, tip=TIP, head=HEAD, left=LISTED):
    """The compare answer's ``commits[]`` for the first-parent path HEAD..LISTED, newest
    first, with the parents REST reports. HEAD itself is the update-branch MERGE (two
    parents: the previous first-parent and main's ``tip``); below it, ``author``
    single-parent author commits; the oldest link's first parent is LISTED. The on-main
    read each merge's second parent triggers is answered by ``_on_main_compare`` (p2 =
    tip, whose merge base with the tip is itself)."""
    chain = []
    child = left
    for i in range(author + 1):
        sha = head if i == author else f"a{i}" + "7" * 39
        chain.append((sha, [child] + ([tip] if i == author else [])))
        child = sha
    return {
        "commits": [{"sha": s, "parents": [{"sha": p} for p in ps]} for s, ps in reversed(chain)],
        "status": "diverged",
        "ahead_by": len(chain),
        "behind_by": 0,
    }


def _on_main_compare():
    # the on-main read this fixture arms is compare/<TIP>...<tip>: p2 IS the tip, so the
    # merge base of p2 and tip is p2 itself ('identical') -- on main.
    return {"merge_base_commit": {"sha": TIP}, "status": "identical", "ahead_by": 0, "behind_by": 0}


def test_merged_and_closed_and_draft_entries_skip():
    for state, draft in (("merged", False), ("closed", False), ("open", True)):
        fake = green()
        fake.prs[111] = pr(111, HEAD, state=state, draft=draft, base="0" * 40)
        gate_answer(fake, GREEN)
        plan = qu.fire(fake, REPO, ISSUE, None)
        assert plan.action == "no-op", (state, draft)
        assert not any("PUT" in " ".join(c) for c in fake.calls)


def test_own_diff_changed_drops_the_entry():
    # the queue line lists the sha the coordinator JUDGED (LISTED), the PR's head has moved
    # on (HEAD) with a changed own diff: an author commit landed after the judgment, so
    # step 4 drops the entry. The listed sha is queued as its 9-char prefix and expanded by
    # the commits read, so both hashes are real revs here.
    fake = green(queue=f"111@{LISTED[:9]}")
    fake.prs[111] = pr(111, HEAD, base="0" * 40)
    gate_answer(fake, GREEN)
    fake.diffs = {LISTED: diff_for(LISTED), HEAD: diff_for(HEAD, "+changed\n")}
    fake.compares[(LISTED, HEAD)] = _r278_chain(author=1)
    plan = qu.fire(fake, REPO, ISSUE, None)
    assert plan.action == "no-op"  # the author commit dropped the entry
    assert not any("PUT" in " ".join(c) for c in fake.calls)


def test_own_diff_carry_updates():
    fake = green(queue=f"111@{LISTED[:9]}")
    fake.prs[111] = pr(111, HEAD, base="0" * 40)
    gate_answer(fake, GREEN)
    fake.diffs = {LISTED: diff_for(LISTED), HEAD: diff_for(HEAD)}  # distinct index lines,
    # but ur106_diff_hash drops index lines and blanks hunk headers, so both hash equal:
    # this asserts the FILTER, not the sha coincidence.
    assert qu.snap.ur106_diff_hash(diff_for(LISTED)) == qu.snap.ur106_diff_hash(diff_for(HEAD))
    # a carried head skips the subset read entirely: hash equal, no chain compare fired.
    plan = qu.fire(fake, REPO, ISSUE, None)
    assert plan.action == "update"
    assert not any(f"/compare/{LISTED}...{HEAD}" in " ".join(c) for c in fake.calls)


def test_a_failed_read_skips_instead_of_deciding():
    fake = green()
    fake.prs[111] = pr(111, HEAD, base="0" * 40)
    fake.fail("pulls/111", "gh: HTTP 502")  # the PR read itself fails
    plan = qu.fire(fake, REPO, ISSUE, None)
    assert plan.action == "no-op"
    assert any("pr read" in e for e in plan.entries[0].errors)


def test_own_diff_hash_needs_no_merge_base_call():  # r5 B1+B3
    # r5 B1+B3, pinned at the command contract: the old _hash_at ran `git merge-base
    # origin/main <rev>` whose stdout rides unstripped into the diff's range arg (git 128,
    # _hash_at never produced a hash), and it could not run at all under the workflow's
    # depth-1 checkout. The rebuilt _hash_at calls NO merge-base: it reads each rev's
    # merge-base off the server-side three-dot compare (the _hash_own per-rev semantics,
    # with the API replacing the local ref), expands a short listed sha through a commits
    # read, fetches exactly the revs at depth 1, and diffs base..rev. The fake refuses a
    # merge-base command (nothing scripts it) and refuses a non-sha fetch/diff arg, so any
    # regression reappears as a failing test, not as a live git 128.
    fake = green(queue=f"111@{LISTED[:9]}")
    fake.prs[111] = pr(111, HEAD, base="0" * 40)
    gate_answer(fake, GREEN)
    fake.diffs = {LISTED: diff_for(LISTED), HEAD: diff_for(HEAD)}  # a carry, as everywhere
    plan = qu.fire(fake, REPO, ISSUE, None)
    assert plan.action == "update"
    git_cmds = [" ".join(c) for c in fake.calls if c[0] == "git"]
    assert not any("merge-base" in c for c in git_cmds), git_cmds
    fetched = sorted(
        {m for c in git_cmds if " fetch " in f" {c} " for m in re.findall(r"[0-9a-f]{40}", c)}
    )
    # each fetch carries base AND rev (`git fetch origin <base> <rev>`), so the union is
    # the two revs plus their bases; with the shared-default base (TIP) that is 3 shas.
    assert fetched == sorted({TIP, LISTED, HEAD}), fetched
    ranges = sorted(
        re.search(r"\b[0-9a-f]{40}\.\.[0-9a-f]{40}\b", c).group(0)
        for c in git_cmds
        if " git diff " in f" {c} "
    )
    assert ranges == sorted({f"{TIP}..{LISTED}", f"{TIP}..{HEAD}"}), ranges  # shas, not refs
    assert any("/compare/" in " ".join(c) for c in fake.calls)


def test_own_diff_hash_base_comes_from_the_compare_answer():  # r5 B1+B3
    # the merge-base the hash diffs against is the COMPARE's, not a ref: script the listed
    # sha's compare to answer a base OLDER than main's tip and assert the range arg uses
    # it -- a base roll that carries (the coordinator's per-rev _hash_own semantics) must
    # not be readable as carry:no. The needle is the '...<rev>' tail: unique to the compare
    # read (the commits/<rev> expansion read has no ellipsis before the sha).
    fake = green(queue=f"111@{LISTED[:9]}")
    fake.prs[111] = pr(111, HEAD, base="0" * 40)
    gate_answer(fake, GREEN)
    old_main = "9" * 40  # the listed sha forks from an older main than the current tip
    fake.diffs = {LISTED: diff_for(LISTED), HEAD: diff_for(HEAD)}
    fake.rules["..." + LISTED[:9]] = json.dumps({"merge_base_commit": {"sha": old_main}})
    plan = qu.fire(fake, REPO, ISSUE, None)
    assert plan.action == "update"
    ranges = [
        re.search(r"\b([0-9a-f]{40})\.\.([0-9a-f]{40})\b", " ".join(c)).groups()
        for c in fake.calls
        if c[:2] == ["git", "diff"]
    ]
    assert (old_main, LISTED) in ranges, ranges  # the listed sha diffs against ITS base
    assert (TIP, HEAD) in ranges, ranges  # the head rev still uses the fresh tip's


# -- ruling 278: the subset carry, in the queue's REST shapes ----------------


def _r278_stage(fake, head_extra=""):
    """The shared r278 stage: LISTED's own diff adds two lines; HEAD's keeps only the
    ``kept`` one and adds ``head_extra``; the chain LISTED..HEAD is one update-branch
    merge of main. Content lines differ per rev, so the HASHES are unequal (the subset
    path runs only after the hash path says no). The merge-bases model the roll's real
    shape: LISTED forks from an OLDER main (``base``), and HEAD -- one update-branch
    merge later -- sits on main's tip, so its merge-base with main is the tip (the
    fake's default compare answer). Main's own change between the two merge-bases is
    then the real range ``base..tip``, what the roll brought in. Returns that base."""
    base = "9" * 40
    fake.rules[f"compare/{TIP}..." + LISTED[:9]] = json.dumps({"merge_base_commit": {"sha": base}})
    fake.compares[(LISTED, HEAD)] = _r278_chain()
    fake.compares[(TIP, TIP)] = _on_main_compare()
    fake.diffs = {
        LISTED: diff_for(LISTED, "+added line\n+kept line\n"),
        HEAD: diff_for(HEAD, "+kept line\n" + head_extra),
        f"{base}..{TIP}": diff_for("mainbetween", "+added line\n"),
    }
    return base


def test_a_subset_carry_where_main_holds_the_dropped_pair_updates():
    # the package's case 2: an update-branch merge of main sits between the heads, HEAD's
    # own diff lost one added line the PR had made, and main's own change between the two
    # merge-bases ADDED that very line (same file and sign) -- the roll carried it. Step 4
    # must NOT drop the entry: the update proceeds (ruling 278 box 2).
    fake = green(queue=f"111@{LISTED[:9]}")
    fake.prs[111] = pr(111, HEAD, base="0" * 40)
    gate_answer(fake, GREEN)
    _r278_stage(fake)
    plan = qu.fire(fake, REPO, ISSUE, None)
    assert plan.action == "update", plan.action_note
    assert not any("update-branch" in " ".join(c) for c in fake.calls)  # dry fire (no token)


def test_a_dropped_line_main_does_not_hold_still_drops():
    # the package's case 3: HEAD's diff lost a line main never made -- an author
    # deletion. The subset verdict is no-carry and step 4 keeps dropping the entry.
    fake = green(queue=f"111@{LISTED[:9]}")
    fake.prs[111] = pr(111, HEAD, base="0" * 40)
    gate_answer(fake, GREEN)
    base = _r278_stage(fake)
    fake.diffs[f"{base}..{TIP}"] = diff_for("mainbetween", "+unrelated\n")
    plan = qu.fire(fake, REPO, ISSUE, None)
    assert plan.action == "no-op"
    assert not any("update-branch" in " ".join(c) for c in fake.calls)


def test_a_line_in_the_new_diff_not_in_the_approved_one_drops():
    # the package's case 4: HEAD's diff holds a line LISTED's never had -- author work.
    fake = green(queue=f"111@{LISTED[:9]}")
    fake.prs[111] = pr(111, HEAD, base="0" * 40)
    gate_answer(fake, GREEN)
    _r278_stage(fake, head_extra="+brand new line\n")
    plan = qu.fire(fake, REPO, ISSUE, None)
    assert plan.action == "no-op"
    assert not any("update-branch" in " ".join(c) for c in fake.calls)


def test_an_author_commit_between_the_heads_drops_in_the_queue_too():
    # the package's case 5: the chain holds a single-parent (author) commit -- no-carry
    # from condition 1 alone, before any line multiset is read.
    fake = green(queue=f"111@{LISTED[:9]}")
    fake.prs[111] = pr(111, HEAD, base="0" * 40)
    gate_answer(fake, GREEN)
    _r278_stage(fake)
    fake.compares[(LISTED, HEAD)] = _r278_chain(author=1)
    plan = qu.fire(fake, REPO, ISSUE, None)
    assert plan.action == "no-op"
    assert not any("update-branch" in " ".join(c) for c in fake.calls)


def test_a_failed_subset_read_skips_instead_of_deciding():
    # the package's case 6: a failed on-main read is unknown -- never yes, and never no.
    # Step 4 skips (not-a-decision) rather than dropping on a guess.
    fake = green(queue=f"111@{LISTED[:9]}")
    fake.prs[111] = pr(111, HEAD, base="0" * 40)
    gate_answer(fake, GREEN)
    _r278_stage(fake)
    fake.fail(f"/compare/{TIP}...{TIP}", "gh: HTTP 502")  # the on-main read dies
    plan = qu.fire(fake, REPO, ISSUE, None)
    assert plan.action == "no-op"
    assert not any("update-branch" in " ".join(c) for c in fake.calls)
    assert any("subset" in e for e in plan.entries[0].errors), plan.entries[0].errors


def test_step6_subset_carry_does_not_disarm_auto_merge():
    # box 2's second half: step 6's re-check uses the same subset decision -- an update
    # merge whose own diff carried keeps auto-merge armed, where the old hash equality
    # would have disarmed (the hashes differ by construction: distinct index lines).
    fake = green()
    fake.prs[111] = pr(111, HEAD, base="0" * 40)
    gate_answer(fake, GREEN)
    # across the update: the re-check compares the listed sha (HEAD) against NEW_HEAD --
    # NEW_HEAD's diff lost one added line, the chain HEAD..NEW_HEAD is the update-branch
    # merge itself (NEW_HEAD's parents are HEAD and main's tip), and main's change
    # between the merge-bases (LISTED-era base -> tip) holds it. HEAD forks from the
    # older main; NEW_HEAD sits ON the tip, so only HEAD's base is pinned.
    base = "9" * 40
    fake.rules[f"compare/{TIP}..." + HEAD[:9]] = json.dumps({"merge_base_commit": {"sha": base}})
    fake.compares[(HEAD, NEW_HEAD)] = _r278_chain(head=NEW_HEAD, left=HEAD)
    fake.compares[(TIP, TIP)] = _on_main_compare()
    fake.diffs = {
        HEAD: diff_for(HEAD, "+added line\n+kept line\n"),
        NEW_HEAD: diff_for(NEW_HEAD, "+kept line\n"),
        f"{base}..{TIP}": diff_for("mainbetween", "+added line\n"),
    }
    plan = qu.fire(fake, REPO, ISSUE, "tok-1")
    assert plan.action == "update"
    assert "carry: yes" in plan.action_note, plan.action_note
    assert not getattr(fake, "disarmed", None), "subset carry disarmed auto-merge"
    assert "carry: yes" in fake.comment_body


def test_a_timeout_error_renders_without_the_argv_or_the_token():  # r5 B2
    # r5 B2, pinned at the render: subprocess.TimeoutExpired's str() carries the FULL argv,
    # so a timeout inside real_run would reach the job summary (stdout + GITHUB_STEP_SUMMARY,
    # a public repo) with `-H "Authorization: token <QUEUE_UPDATE_TOKEN>"` in it. real_run
    # must catch the timeout and re-raise CommandError-shaped with the argv truncated to
    # cmd[:3], the same shape every other real_run raise carries. The stub follows the
    # N10 test's pattern: patch subprocess.run, since real_run calls it directly.
    def boom(cmd, **_k):
        raise subprocess.TimeoutExpired(cmd, 120)

    orig = qu.subprocess.run
    qu.subprocess.run = boom
    try:
        qu.real_run(["gh", "api", "graphql", "-H", "Authorization: token sekrit", "-f", "query=x"])
        raise AssertionError("real_run did not raise on a timeout")
    except qu.snap.CommandError as exc:  # NOT a bare TimeoutExpired: _gh_rest/mains read it
        text = qu.snap.error_text(exc)
        assert "Authorization" not in text, text
        assert "sekrit" not in text, text
        assert "graphql" in text  # cmd[:3] still names the call: 'gh api graphql'
        assert "query=" not in text  # the argv beyond cmd[:3] is gone
    finally:
        qu.subprocess.run = orig


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


def test_conflict_422_falls_through_like_409():
    # GitHub documents 422 for the expected_head_sha-mismatch and merge-conflict class of
    # update-branch; both statuses read as "this entry cannot update now" (N2's widening).
    queue = f"111@{HEAD[:9]} 222@{HEAD2[:9]}"
    fake = green(queue=queue)
    fake.prs[111] = pr(111, HEAD, base="0" * 40)
    fake.prs[222] = pr(222, HEAD2, base="0" * 40)
    gate_answer(fake, GREEN)
    fake.update_status = 422
    fake.update_answer = {"message": "head was modified"}
    plan = qu.fire(fake, REPO, ISSUE, "tok-1")
    assert plan.action == "no-op"  # both entries 422ed: stop
    # the note names the second entry's conflict; the first's rode entry 111's errors on
    # the pre-fallthrough plan (rebuilt here), so the fire shape is pinned by the PUT
    # count instead: two PUTs, one fire, both entries tried.
    assert "a second entry conflicted too" in plan.action_note
    assert len([c for c in fake.calls if "update-branch" in " ".join(c)]) == 2
    # n11: the re-decide must DROP the conflicted entry from the queue list, or this fire
    # re-picks #111 and PUTs it again (decide() iterates queue_entries, so the entries-list
    # filter alone cannot stop a re-pick). One PUT per entry, each PR addressed once.
    targets = [
        re.search(r"pulls/(\d+)/update-branch", " ".join(c)).group(1)
        for c in fake.calls
        if "update-branch" in " ".join(c)
    ]
    assert targets == ["111", "222"], targets


def test_a_conflicted_last_entry_is_not_reput_in_the_same_fire():
    # n11's killer shape: ONE queue entry, it conflicts. The re-decide's queue_entries
    # drop is what keeps decide() from seeing it again -- removing that drop re-PUTs the
    # same PR within the fire and reports "a second entry conflicted too" for a queue
    # that only ever held one entry. Pinned red-first against exactly that mutant.
    fake = green(queue=f"111@{HEAD[:9]}")
    fake.prs[111] = pr(111, HEAD, base="0" * 40)
    gate_answer(fake, GREEN)
    fake.update_status = 409
    fake.update_answer = {"message": "merge conflict"}
    plan = qu.fire(fake, REPO, ISSUE, "tok-1")
    assert plan.action == "no-op"
    assert "second entry" not in plan.action_note  # there IS no second entry
    assert len([c for c in fake.calls if "update-branch" in " ".join(c)]) == 1


def test_a_transport_failure_on_the_put_is_not_a_conflict_nor_a_crash():
    # gh exiting with NO status line on stdout (a network death): status 0, not any
    # branch's shape -- the fire stops, reports, writes no comment, and stays red rather
    # than guessing (N2's second half: the raise must not escape to main()'s catch).
    fake = green()
    fake.prs[111] = pr(111, HEAD, base="0" * 40)
    gate_answer(fake, GREEN)
    fake.update_status = 0
    plan = qu.fire(fake, REPO, ISSUE, "tok-1")
    assert plan.action == "update"  # the decision stands; the note says what failed
    assert "answered 0" in plan.action_note
    assert not getattr(fake, "comment_body", None), "commented on a fire that wrote nothing"
    assert not getattr(fake, "armed", None)


def test_real_run_carries_stdout_through_the_raise():
    # N10's production pin: real_run on rc != 0 must carry stdout on the raised error --
    # the --include status line is stdout, and a discard-the-stdout raise reads every
    # HTTP >= 400 answer as status 0 (the reviewer's end-to-end proof).
    proc = subprocess.run(
        [sys.executable, "-c", "print('HTTP/1.1 409 Conflict'); raise SystemExit(1)"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0 and proc.stdout.startswith("HTTP/1.1 409")

    # the real contract through real_run itself, with a stubbed subprocess.run that mimics
    # gh's shape: rc=1, status line on stdout, error on stderr.
    class FakeProc:
        returncode = 1
        stdout = 'HTTP/1.1 409 Conflict\r\n\r\n{"message": "conflict"}'
        stderr = "gh: Not found"

    orig = qu.subprocess.run
    qu.subprocess.run = lambda *_a, **_k: FakeProc()
    try:
        qu.real_run(["gh", "api", "-X", "PUT", "x"])
        raise AssertionError("real_run did not raise on rc=1")
    except qu.snap.CommandError as exc:
        assert getattr(exc, "stdout", "").startswith("HTTP/1.1 409"), (
            "the --include status line did not ride the raise (N10)"
        )
    finally:
        qu.subprocess.run = orig


def test_the_raising_contract_fires_the_fallthrough():
    # N10 end-to-end at the production contract: the fake RAISES on the 409 (stdout
    # carried), and fire() must still fall through to the next entry in the same fire --
    # exactly the behavior the swallow-only shape silently degraded to a status-0 stop.
    queue = f"111@{HEAD[:9]} 222@{HEAD2[:9]}"
    fake = green(queue=queue)
    fake.prs[111] = pr(111, HEAD, base="0" * 40)
    fake.prs[222] = pr(222, HEAD2, base="0" * 40)
    gate_answer(fake, GREEN)
    fake.update_status = 409
    fake.update_answer = {"message": "conflict"}
    plan = qu.fire(fake, REPO, ISSUE, "tok-1")
    assert len([c for c in fake.calls if "update-branch" in " ".join(c)]) == 2, (
        "the raise broke the same-fire fallthrough"
    )
    # the fake answers every PUT with the 409, so both entries conflict and the fire stops
    # as a no-op (R3 note 2: the looser "update or no-op" interval could pass a fire that
    # updated a DIFFERENT entry than the fallthrough's).
    assert plan.action == "no-op"
    assert "a second entry conflicted too" in plan.action_note


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
    fake.compares[(HEAD, NEW_HEAD)] = _r278_chain(
        author=1, head=NEW_HEAD, left=HEAD
    )  # the author commit between the heads: condition 1 fails, no carry
    gate_answer(fake, GREEN)
    plan = qu.fire(fake, REPO, ISSUE, "tok-1")
    assert plan.action == "update" and "carry: no" in plan.action_note
    disarms = [c for c in fake.calls if any("disablePullRequestAutoMerge" in a for a in c)]
    assert len(disarms) == 1
    assert any(a.startswith("Authorization: token tok-1") for a in disarms[0])


# -- step 6: the re-hash across the update ----------------------------------


def test_carry_no_disarms_auto_merge_and_comments():
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
    fake.compares[(HEAD, NEW_HEAD)] = _r278_chain(
        author=1, head=NEW_HEAD, left=HEAD
    )  # the author commit between the heads: condition 1 fails, no carry
    plan = qu.fire(fake, REPO, ISSUE, "tok-1")
    assert getattr(fake, "disarmed", None), "auto-merge stayed armed on carry: no"
    assert "disablePullRequestAutoMerge" in fake.disarmed
    assert "carry: no" in plan.action_note
    # step 7's comment goes out on this path too (N3): item 6 makes it the own-diff
    # comparison UR-106's condition 1 asks the coordinator to quote, and the carry:no
    # handoff is exactly where the coordinator needs it, on the PR itself.
    assert getattr(fake, "comment_body", None), "no step-7 comment on the carry:no path"
    assert "carry: no" in fake.comment_body
    assert NEW_HEAD[:9] in fake.comment_body


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
    # r288: the main-CI read's path is the CI workflow's own runs; the needle must name
    # the path production reads or it never fires and this test certifies nothing.
    fake.fail("actions/workflows/ci.yml/runs?", "gh: HTTP 502")
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
