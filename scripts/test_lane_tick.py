#!/usr/bin/env python3
"""Tests for scripts/uplevel/lane_tick.py (ruling 181), with no network.

Run explicitly; outside testpaths (like every scripts/test_*.py gate suite):

    uv run python -m pytest scripts/test_lane_tick.py -q

One seam: ``lane_tick.build(run, clock, repo, sandbox)`` takes the runner, the clock, the repo and
the sandbox, so nothing here patches a module global or reaches the network. The fake answers by
command shape, records every call, and raises on a command nobody scripted -- so a new read shows up
as a failing test instead of a live API call. Each test changes one answer of the shared green
scenario, as ``test_coordinator_snapshot.py``'s do.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "uplevel" / "lane_tick.py"
SNAP = REPO_ROOT / "scripts" / "uplevel" / "coordinator_snapshot.py"
STATUS = REPO_ROOT / "scripts" / "uplevel" / "status_draft.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# lane_tick imports its sibling by the bare module name (it puts its own directory on sys.path), so
# the sibling is registered under that name first -- exactly the name the script will find.
snap = _load("coordinator_snapshot", SNAP)
tick = _load("lane_tick", SCRIPT)
status = _load("status_draft", STATUS)
# The footer's writer, loaded after `lane_tick` so it reads the footer through this same module.
post = _load("post_record", REPO_ROOT / "scripts" / "uplevel" / "post_record.py")

NOW = datetime(2026, 10, 15, 9, 30, 0, tzinfo=UTC)
REPO = "o/r"
SANDBOX = "agent-uplevel-ops-b"
MY_BRANCH = "uplevel/r181-lane-tick-digest"
OTHER_BRANCH = "uplevel/lane-defect-events-stats-soft-deleted"
THEIRS = "uplevel/lane-backend-something"
MY_HEAD = "a" * 40
MINE2_HEAD = "d" * 40
THEIRS_HEAD = "b" * 40
BASE = "c" * 40
BEAT_ID = 6138656635
NEW_BEAT_ID = 6199999999  # what the fake answers to --beat's write
GATE_RUN = 900
CURSOR = "2026-10-15T07:30:00Z"  # the coordinator's read-through: the digest's comment window
BEAT_AT = "2026-10-15T09:27:00Z"  # my beat, 3 minutes old


def t(delta: timedelta) -> str:
    return snap.iso(NOW + delta)


def heartbeat(agent, minutes, prose=None, cid=BEAT_ID):
    """A beat in the live shape: marker, one prose line, then the optional BLOCKER/read-through."""
    body = f"<!-- heartbeat:{agent} -->\n" + (
        prose or f"{agent.removeprefix('agent-uplevel-')} · 09:2xZ · working"
    )
    return {
        "id": cid,
        "user": {"login": "mikesvoboda"},
        "created_at": t(timedelta(days=-2)),
        "updated_at": t(timedelta(minutes=-minutes)),
        "body": body,
    }


def coordinator(minutes=5, cid=1):
    return heartbeat(
        "agent-uplevel-coordinator",
        minutes,
        f"coordinator · 09:2xZ · tick\nread-through: {CURSOR}",
        cid=cid,
    )


def comment(cid, number, body, when, pr=False, user="mikesvoboda"):
    kind = "pull" if pr else "issues"
    return {
        "id": cid,
        "issue_url": f"https://api.github.com/repos/{REPO}/issues/{number}",
        "html_url": f"https://github.com/{REPO}/{kind}/{number}#issuecomment-{cid}",
        "user": {"login": user},
        "created_at": when,
        "updated_at": when,
        "body": body,
    }


def gate(conclusion="SUCCESS", status_="COMPLETED", run=GATE_RUN):
    return {
        "__typename": "CheckRun",
        "name": "CI Gate (Required Checks)",
        "status": status_,
        "conclusion": conclusion,
        "startedAt": t(timedelta(minutes=-6)),
        "detailsUrl": f"https://github.com/{REPO}/actions/runs/{run}/job/5",
    }


def filler():
    return {
        "__typename": "CheckRun",
        "name": "Backend Unit Tests",
        "status": "COMPLETED",
        "conclusion": "SUCCESS",
        "startedAt": t(timedelta(minutes=-6)),
        "detailsUrl": f"https://github.com/{REPO}/actions/runs/901/job/1",
    }


def job(conclusion="SUCCESS", run=GATE_RUN, name="Backend Unit Tests"):
    """A non-gate check of the gate's OWN run: SUCCESS on a ready run, SKIPPED on a draft run."""
    return {**filler(), "name": name, "conclusion": conclusion, "detailsUrl": f"https://github.com/{REPO}/actions/runs/{run}/job/2"}  # fmt: skip


def pr(number, *, labels, head, draft=True, merge="BEHIND", rollup=None, title="pr", armed=False):
    """A row of the snapshot's batched ``gh pr list`` (the verdict-carrying read)."""
    return {
        "number": number,
        "title": title,
        "isDraft": draft,
        "labels": [{"name": n} for n in labels],
        "headRefOid": head,
        "mergeStateStatus": merge,
        "autoMergeRequest": {"mergeMethod": "MERGE"} if armed else None,
        "statusCheckRollup": rollup if rollup is not None else [gate()],
    }


def head_row(number, branch, title="pr"):
    """A row of the digest's OWN ``gh pr list`` -- the one that asks for headRefName."""
    return {"number": number, "title": title, "headRefName": branch}


MINE2 = "[r151] soft-deleted defect events"
MINE1 = "[r181] the lane-tick digest"
NOTMINE = "theirs"
GREEN_PRS = [
    pr(7158, labels=["lane:ops", "cell:b"], head=MINE2_HEAD, draft=False, merge="DIRTY", title=MINE2),
    pr(7164, labels=["lane:ops", "cell:b"], head=MY_HEAD, title=MINE1),
    # Another lane's ready PR still carrying a pre-ruling-198 review label: never listed, never read.
    pr(7200, labels=["lane:backend", "review:ops-b"], head=THEIRS_HEAD, draft=False, title=NOTMINE),
]  # fmt: skip
GREEN_HEADS = [
    head_row(7158, OTHER_BRANCH, MINE2),
    head_row(7164, MY_BRANCH, MINE1),
    head_row(7200, THEIRS, NOTMINE),
]  # fmt: skip
OLD_HEAD = "e" * 40  # a head #7158 had before; an approval naming it is judged by UR-106's carry
# The review form roles/lane.md gives, naming the head it read on its first line as the live ones do.
APPROVE = f"Review: approve `{MINE2_HEAD[:9]}`\nReviewer lane: ops (UR-89 subagent)\nDone when: all observed\nContract: rules 1-5 — ok\n- **Plan text:** none.\nNotes:\n"  # fmt: skip
SAME_DIFF = "diff --git a/backend/x.py b/backend/x.py\n@@ -1 +1 @@\n-a\n+b\n"

# The rows below carry main's roles/lane.md shape (agent | tier | queue | review label), shortened.
# `none` is a real label value -- a cell with no review queue -- and the roster is 141 columns wide.
ROSTER = """\
| agent              | tier      | queue                                    | review label     |
| ------------------ | --------- | ---------------------------------------- | ---------------- |
| `uplevel-coordinator` | fast   | routing (`roles/coordinator.md`)           | none             |
| `uplevel-backend`   | fast     | `[r149d]`, `[r129]`                        | `review:backend` |
| `uplevel-ops-a`     | fast     | `OB.3`, `[r164a]`, `O3.1`                  | `review:ops-a`   |
| `uplevel-ops-b`     | fast     | `[r157]`, `[r151]`, `F2.3` UI (OP-3), `[r181]`, `[r172]`, `O3.4` | `review:ops-b` |
| `uplevel-heavy-b`   | strongest | `B2.3` once `O2.4` passes                 | none             |
"""  # fmt: skip
MAP = (
    "| 177 | ruling 177 (record 6172198207) |\n"
    "| 188 | package [r157] (record 6182950505) |\n"
    "\nSee ruling 190 for why the map is the plan.\n"
)
PKG = """\
### [r157] O2.4 independent plan builds

**Flags:** none. **Assigned:** `uplevel-ops-b`, first on its queue. **PR:** #7087. (rulings 157)

- [x] box done

### [r164a] The coordinator's paperwork moves into scripts

**Flags:** none. **Assigned:** `uplevel-ops-a`, next on its queue after `O2.5`.
**Depends on:** none. **PR:** none yet. (ruling 164)

- [ ] box

### [r181] The lane-tick digest

**Flags:** none. **Assigned:** `uplevel-ops-b`. **PR:** none yet. (ruling 181)

- [ ] box

### [r172] A per-module import budget

**Flags:** none. **Assigned:** `uplevel-ops-b`, after `[r157]`; ops-a reviews. **PR:**
none yet. (ruling 172; issue #7102)

- [ ] box
"""  # fmt: skip
DF_OK = (
    "Filesystem      Size  Used Avail Use% Mounted on\n"
    "/dev/vda         20G   16G  3.9G  81% /\n"
    "/dev/vdb        9.8G  8.2G  1.6G  84% /var/lib/docker\n"
)
DF_OVER = DF_OK.replace("16G  3.9G  81% /", "19G  900M  92% /")


class Fake:
    """Answers by command shape, records every call, raises on a command nobody scripted."""

    def __init__(self, **over):
        self.calls: list[list[str]] = []
        self.rules: dict[str, object] = {}
        self.beats = over.get("beats", [coordinator(), heartbeat(SANDBOX, over.get("beat_min", 3))])
        self.repo_comments = over.get("repo_comments", [])
        self.owner_comments = over.get("owner_comments", [])
        self.prs = over.get("prs", GREEN_PRS)
        self.heads = over.get("heads", GREEN_HEADS)
        self.branches = over.get("branches", ["main", MY_BRANCH, OTHER_BRANCH])
        # a PR's WHOLE thread; the digest's windowed reads get the part GitHub's `since` would send
        self.pr_comments = over.get("pr_comments", {})
        # UR-106's own-diff inputs: the PR's files, and each rev's diff (default: identical diffs,
        # i.e. a carry -- a test that wants an author change gives the rev a different diff)
        self.files = over.get("files", ["backend/x.py"])
        self.diffs = over.get("diffs", {})
        self.pr_reviews = over.get("pr_reviews", {})
        self.df = over.get("df", DF_OK)
        self.map = over.get("map", MAP)
        self.packages = over.get("packages", PKG)
        self.roster = over.get("roster", ROSTER)
        self.behind = over.get("behind", "3")
        self.commits = over.get("commits", "")
        self.jobs = over.get("jobs", [])
        self.rollup_reread = over.get("rollup_reread", {})

    def fail(self, needle: str, message: str = "gh: HTTP 502 upstream") -> None:
        self.rules[needle] = snap.CommandError(message)

    def __call__(self, cmd):
        cmd = [str(x) for x in cmd]
        self.calls.append(cmd)
        joined = " ".join(cmd)
        for needle, answer in self.rules.items():
            if needle in joined:
                if isinstance(answer, Exception):
                    raise answer
                return answer
        return self.default(cmd)

    def default(self, cmd):
        if cmd[:2] == ["df", "-h"]:
            return self.df
        if cmd[:3] == ["git", "ls-tree", "origin/main"]:
            # Existence, asked the way the tool asks it: a non-empty answer only for a package file
            # this fake carries. A lane the fixture has no file for gets "", which is the NOTE arm.
            ref = cmd[-1].lstrip(":/")
            return f"100644 blob abc\t{ref}\n" if ref.endswith("ops.md") else ""
        if cmd[:2] == ["git", "show"]:
            # Raises on a doc nobody scripted (the class contract), rather than answering "" the way
            # this arm once did: a fourth `git show` added to the tool would have read as an EMPTY
            # file and every section keyed off it would have passed while reading nothing.
            doc = cmd[-1].rsplit("/", 1)[-1]
            docs = {"ruling-map.md": self.map, "lane.md": self.roster, "ops.md": self.packages}
            if doc not in docs:
                raise AssertionError(f"unscripted git show: {cmd[-1]}")
            return docs[doc]
        if cmd[:2] == ["git", "branch"]:
            return "\n".join(self.branches) + "\n"
        if cmd[:2] == ["git", "rev-list"]:
            return self.behind + "\n"
        if cmd[:2] == ["git", "merge-base"]:
            return BASE + "\n"
        if cmd[:2] == ["git", "fetch"]:
            return ""
        if cmd[:2] == ["git", "log"]:
            return self.commits
        if cmd[:2] == ["git", "diff"]:
            # `git diff <base>..<rev> -- <files>`: the UR-106 own diff of one rev
            return self.diffs.get(cmd[2].split("..", 1)[1], SAME_DIFF)
        if cmd[:3] == ["gh", "pr", "list"]:
            # The snapshot's batch and the digest's own read differ by exactly the fields asked for.
            return json.dumps(self.heads if "headRefName" in cmd[-1] else self.prs)
        if cmd[:3] == ["gh", "pr", "view"]:
            if cmd[-1] == "files":
                return json.dumps({"files": [{"path": f} for f in self.files]})
            return json.dumps({"statusCheckRollup": self.rollup_reread[int(cmd[3])]})
        if cmd[:3] == ["gh", "api", "-X"]:
            # `--beat`'s one write, answered the way gh answers it: the comment it wrote.
            return json.dumps({"id": NEW_BEAT_ID})
        if cmd[:2] == ["gh", "api"]:
            answer = self.api(cmd[2])
            if "--jq" in cmd:
                answer = json.dumps(self.jq(json.loads(answer), cmd[cmd.index("--jq") + 1]))
            return answer
        raise AssertionError(f"unexpected command {cmd}")

    @staticmethod
    def jq(rows, expr):
        """gh applies `--jq` client-side, so the fake must too, or a pin about which comments are
        reviews would measure the fixture. Only the snapshot's verdict filter is scripted."""
        if expr != snap.REVIEWS_JQ:
            raise AssertionError(f"unscripted jq: {expr}")
        return [
            {"id": c["id"], "created_at": c["created_at"], "user": c["user"]["login"], "body": c["body"]}
            for c in rows
            if c["body"].startswith("Review:")
        ]  # fmt: skip

    def api(self, path):
        if "/issues/6958/comments" in path:
            return json.dumps(self.beats)
        if "/issues/6854/comments" in path:
            return json.dumps(self.owner_comments)
        if "/issues/comments?" in path:
            return json.dumps(self.repo_comments)
        if "/actions/runs/" in path and "/jobs" in path:
            return json.dumps({"jobs": self.jobs})
        if m := re.search(r"/pulls/([0-9]+)/reviews", path):
            return json.dumps(self.pr_reviews.get(int(m.group(1)), []))
        if m := re.search(r"/issues/([0-9]+)/comments", path):
            number = int(m.group(1))
            rows = self.pr_comments.get(number, [])
            if w := re.search(r"since=([\w:.Z-]+)", path):
                # GitHub's `since` filters by updated_at; the fake has to, or a pin about "older
                # than the beat is not counted" would be measuring the fixture instead of the tool.
                rows = [r for r in rows if r["updated_at"] >= w.group(1)]
            return json.dumps(rows)
        raise AssertionError(f"unexpected api {path}")

    def asked(self, needle: str) -> list[str]:
        return [" ".join(c) for c in self.calls if needle in " ".join(c)]


def run_tick(**over) -> tuple[Fake, str]:
    fake = Fake(**over)
    return fake, "\n".join(tick.build(fake, lambda: NOW, REPO, over.get("sandbox", SANDBOX)))


def text(**over) -> str:
    return run_tick(**over)[1]


def has(out: str, needle: str) -> list[str]:
    return [ln for ln in out.splitlines() if needle in ln]


def row(out: str, number: int) -> str:
    return " ".join(has(out, f"#{number} "))


# --- the one seam ---------------------------------------------------------------------------


def test_build_needs_only_a_runner_a_clock_a_repo_and_a_sandbox():
    # Everything the tick reads arrives through one seam, so a test needs no monkeypatching and
    # main() cannot hand the renderer a different type than it expects. The first live run hit
    # exactly that: a built dict passed into a function that read `.data` off a Snapshot object.
    fake, out = run_tick()
    assert out.startswith("# lane tick agent-uplevel-ops-b")
    assert all(isinstance(ln, str) for ln in out.splitlines())
    assert fake.asked("df -h")


def test_main_prints_the_same_digest_through_the_injected_runner(capsys):
    fake = Fake()
    assert tick.main(["--sandbox", SANDBOX, "--repo", REPO], run=fake, clock=lambda: NOW) == 0
    printed = capsys.readouterr().out
    assert "#7164" in printed and "holding open claim" in printed


# --- identity -------------------------------------------------------------------------------


def test_my_lane_cell_and_review_label_come_from_the_roster_row():
    # Every agent posts with the owner's token (UR-168), so the roster row -- not the author, not a
    # label -- is what says which lane's work is mine and which label routes reviews to me.
    ids = tick.identities(ROSTER, SANDBOX)
    assert (ids["lane"], ids["cell"], ids["review_label"]) == ("ops", "b", "review:ops-b")


def test_a_one_cell_lanes_row_has_no_cell():
    ids = tick.identities(ROSTER, "agent-uplevel-backend")
    assert (ids["lane"], ids["cell"], ids["review_label"]) == ("backend", "", "review:backend")


def test_my_roster_queue_is_the_order_the_digest_reads_packages_in():
    # The queue tokens must be spelled the way the package block headers are: the roster writes
    # `[r157]` and the file writes `### [r157]`, and a token that keeps its brackets matches none
    # of them -- so every package reads as "not on my queue" and nothing is ever offered.
    assert tick.identities(ROSTER, SANDBOX)["queue"] == [
        "r157",
        "r151",
        "F2.3",
        "r181",
        "r172",
        "O3.4",
    ]


def test_a_cell_whose_review_label_is_none_still_reads_instead_of_erroring():
    # `none` is a real value on main's roster (coordinator, heavy-a, heavy-b, operator), and the
    # roster keeps the column after ruling 198. A row parser that dropped it would print
    # `ERROR identities` on every heavy-tier tick.
    out = text(sandbox="agent-uplevel-heavy-b", beats=[heartbeat("agent-uplevel-heavy-b", 3)])
    assert has(out, "== mine (") and not has(out, "ERROR identities")


def test_there_is_no_review_queue_section_and_no_read_for_one():
    # Ruling 198: each PR's one review is its author's UR-89 subagent; no PR is routed to another
    # lane. #7200 still carries a pre-ruling `review:ops-b` label and is not on my branches: it is
    # neither listed nor read -- not its rows, not its thread, not its gate's jobs.
    fake, out = run_tick()
    assert not has(out, "review:") and not has(out, "review queue")
    assert not has(out, "#7200")
    assert fake.asked("issues/7200") == [] and fake.asked("pulls/7200") == []


def test_a_sandbox_with_no_roster_row_says_so_on_one_line():
    out = text(sandbox="agent-uplevel-nobody")
    # The message names the sandbox that missed, so the fix is "the roster has no row for X", not
    # "identities broke" -- and the report is that one line, because nothing downstream is keyable.
    assert out.splitlines() == ["ERROR identities: no roster row for sandbox agent-uplevel-nobody"]


# --- 2. my beat, the coordinator, disk -------------------------------------------------------


def test_my_beat_prints_its_id_age_and_prose():
    out = text(
        beats=[
            coordinator(),
            heartbeat(SANDBOX, 3, f"{SANDBOX} · 09:2xZ · working #7164 · [r181] box 2"),
        ]
    )
    line = " ".join(has(out, "heartbeat id="))
    assert f"id={BEAT_ID}" in line and "age 3.0m" in line and "working #7164" in line


def test_a_missing_beat_for_my_sandbox_is_reported_not_left_blank():
    assert has(text(beats=[coordinator()]), f"ERROR heartbeats: no beat for {SANDBOX}")


# --- the --sandbox spelling ---------------------------------------------------------------
# Both spellings are live on #6958 (measured: `uplevel-ops-a`, `uplevel-ops-b`, `uplevel-operator`
# beat BARE; `agent-uplevel-backend`, `-frontend`, `-docs`, `-coordinator`, `-heavy-a/b` beat
# PREFIXED) and `--sandbox` arrives as either -- the hostname is what `$SANDBOX_NAME` gives and so
# what the role docs' `<your-sandbox>` resolves to. These go through `build`, not the helper: the
# bug was the two lookups INSIDE build disagreeing, and a test that called the helper directly -- as
# the held_claims A/B did -- could not see it.


@pytest.mark.parametrize(
    ("arg", "beat_key"),
    [
        # the docs' path: hostname in, bare beat on the issue (ops-a/ops-b/operator's real shape)
        ("agent-uplevel-ops-b", "uplevel-ops-b"),
        # the reverse: marker name in, prefixed beat (backend/frontend/docs/heavy's real shape)
        ("uplevel-ops-b", "agent-uplevel-ops-b"),
        # and the two that already agreed, so the fix is shown not to need them
        ("agent-uplevel-ops-b", "agent-uplevel-ops-b"),
        ("uplevel-ops-b", "uplevel-ops-b"),
    ],
)
def test_either_sandbox_spelling_finds_my_beat(arg, beat_key):
    out = text(sandbox=arg, beats=[coordinator(), heartbeat(beat_key, 3)])
    assert has(out, "heartbeat id="), out
    assert not has(out, "ERROR heartbeats"), out


def test_two_beats_naming_me_resolve_to_the_freshest_not_the_first():
    # Identity-matching makes two spellings ONE agent, so a stale second row becomes reachable. The
    # heartbeat endpoint is not reliably sorted, so "first match" would be a coin flip -- the stale
    # row is placed LAST here, the ordering that would make an arbitrary pick print the wrong age.
    fresh = heartbeat("uplevel-ops-b", 3, cid=BEAT_ID)
    stale = heartbeat("agent-uplevel-ops-b", 400, cid=999)
    out = text(beats=[coordinator(), stale, fresh])
    line = " ".join(has(out, "heartbeat id="))
    assert f"id={BEAT_ID}" in line and "age 3.0m" in line, line
    assert "id=999" not in out, "the stale spelling won"


def test_the_comment_window_is_my_beat_under_either_spelling():
    # The graver half: a missed beat made `since` fall back to the COORDINATOR's cursor, so step 4's
    # `Nc/Nr since beat` was measured from a referent that is not my beat -- silently. Here the
    # coordinator's read-through is NEWER than my beat and a comment lands in between, so the
    # fallback reads 0c while the beat's own watermark reads 1c: the undercount, made visible.
    beats = [
        heartbeat("uplevel-ops-b", 3),
        heartbeat(
            "agent-uplevel-coordinator",
            1,
            "coordinator · 09:2xZ · tick\nread-through: " + t(timedelta(minutes=-1)),
            cid=1,
        ),
    ]
    between = comment(91, 7158, "Reviewer lane: ops-a\na flag", t(timedelta(minutes=-2)))
    for arg in ("agent-uplevel-ops-b", "uplevel-ops-b"):
        fake, out = run_tick(sandbox=arg, beats=beats, pr_comments={7158: [between]}, pr_reviews={})
        read = [c for c in fake.asked("issues/7158/comments") if "since=" in c]
        assert read and f"since={BEAT_AT}" in read[0], f"{arg}: window {read[:1]}"
        assert "1c/0r since beat" in row(out, 7158), f"{arg}: {row(out, 7158)}"


def test_the_coordinators_age_prints_and_a_fresh_one_raises_no_rule():
    assert has(text(), "coordinator age 5.0m") and not has(text(), "UR-162")


def test_a_stale_coordinator_row_does_not_raise_a_ur162_that_is_not_owed():
    # The coordinator keeps one row but its marker spelling can leave a stale duplicate behind, and
    # the endpoint is not sorted. A first-match pick of the STALE row would trip UR-162 (age > 20m ->
    # post a URGENT PATH) that the coordinator's actual fresh beat does not owe. Stale row placed
    # last, so only a real freshest-wins tie-break avoids the false raise.
    # Two rows must carry DIFFERENT spellings to survive `beats = {h["agent"]: h ...}`, which is
    # keyed by the marker string: the same spelling twice collapses to one row and the pin would
    # pass without the tie-break existing at all.
    out = text(
        beats=[
            heartbeat("uplevel-ops-b", 3),
            heartbeat(
                "uplevel-coordinator",
                400,
                "coordinator · 08:0xZ · tick\nread-through: " + CURSOR,
                cid=1,
            ),  # stale, bare spelling
            coordinator(2, cid=2),  # fresh, prefixed spelling
        ]
    )
    assert has(out, "coordinator age 2.0m"), out
    assert not has(out, "UR-162"), out


def test_a_coordinator_older_than_twenty_minutes_points_at_ur162():
    assert has(text(beats=[coordinator(34), heartbeat(SANDBOX, 3)]), "post one")


def test_a_live_urgent_path_on_the_owner_issue_suppresses_the_raise_instruction():
    # UR-162: one URGENT PATH per hour, so the digest reads #6854 to see whether one is already up.
    out = text(
        beats=[coordinator(34), heartbeat(SANDBOX, 3)],
        owner_comments=[
            comment(
                99,
                6854,
                "URGENT PATH · coordinator stale (`6188196491`).",
                t(timedelta(minutes=-9)),
            )
        ],
    )
    assert not has(out, "post one") and has(out, "already on record")  # fmt: skip


def test_a_close_is_not_a_live_raise():
    # Measured live on #6854: a close reads "**URGENT PATH closed — coordinator stale (`61...`)**"
    # and shares the first ELEVEN characters with a raise. A prefix test reads the close as a live
    # raise and stays silent while the coordinator is stale with no raise on record -- the one case
    # the rule exists for.
    out = text(
        beats=[coordinator(34), heartbeat(SANDBOX, 3)],
        owner_comments=[
            comment(
                99,
                6854,
                "**URGENT PATH closed — coordinator stale (`6188196491`).**",
                t(timedelta(minutes=-9)),
            )
        ],
    )
    assert has(out, "post one")  # fmt: skip


def test_a_raise_older_than_the_hour_does_not_suppress_a_new_one():
    out = text(
        beats=[coordinator(34), heartbeat(SANDBOX, 3)],
        owner_comments=[
            comment(99, 6854, "URGENT PATH · coordinator stale", t(timedelta(minutes=-75)))
        ],
    )
    assert has(out, "post one")


def test_disk_under_the_ceiling_names_no_rule_and_reads_both_mounts_in_one_call():
    fake, out = run_tick()
    assert has(out, "disk / 81%") and has(out, "disk /var/lib/docker 84%")
    assert not has(out, "UR-180")
    assert fake.asked("df -h") == [f"df -h {' '.join(tick.MOUNTS)}"]


def test_disk_over_ninety_points_at_ur180s_order_and_never_at_a_full_prune():
    # Ruling 176's prohibition is on a ROUTINE full prune (it re-pulls base images and CI has already
    # hit Docker Hub's anonymous pull limit), so the digest must send the lane to UR-180's ORDER --
    # which legitimately names builder/image prunes itself. A bare `"prune" not in warn` would
    # enforce the wrong rule and pass on a line that said nothing at all. Pin what it MUST say, then
    # the one command it must never name.
    lines = has(text(df=DF_OVER), "disk")
    warn = " ".join(lines)
    assert "92%" in warn  # the mount over the ceiling is named with its number
    assert "UR-180" in warn and re.search(r"order", warn, re.I), warn
    assert not re.search(r"system prune", warn, re.I), warn


def test_a_mount_the_answer_does_not_carry_is_named_unread_not_skipped():
    # An absent line reads as "no disk problem" to a lane that cannot tell it was never fetched.
    out = text(df="Filesystem Size Used Avail Use% Mounted on\n/dev/vda 20G 16G 3.9G 81% /\n")
    assert has(out, "disk /var/lib/docker unread")


# --- 1. ruling 177's filter ------------------------------------------------------------------


def test_a_binding_record_the_map_carries_by_ruling_number_is_not_printed():
    out = text(
        owner_comments=[
            comment(
                11, 6854, "BINDING NOW · ruling 188 · ops-b: keep going", t(timedelta(hours=-2))
            )
        ]
    )
    assert not has(out, "BINDING NOW")  # fmt: skip


def test_a_binding_record_the_map_does_not_carry_is_printed_with_its_id():
    out = text(
        owner_comments=[
            comment(12, 6854, "BINDING NOW · ruling 189 · ops-b: stop", t(timedelta(hours=-2)))
        ]
    )
    assert has(out, "id=12") and has(out, "ruling 189")


def test_a_record_the_map_carries_by_comment_id_alone_is_not_printed():
    # Ruling 177 carries either form; some map rows name a record by comment id only.
    out = text(
        owner_comments=[
            comment(13, 6854, "BINDING NOW · no number on this line", t(timedelta(hours=-2)))
        ],
        map=MAP + "\nseen 13 here\n",
    )
    assert not has(out, "id=13")  # fmt: skip


def test_a_ruling_number_that_appears_in_the_map_only_in_prose_is_not_carriage():
    # The map quotes ruling numbers in prose as well as in `| nn |` rows. A prose mention read as
    # carriage hides a live ruling from the one check that exists to surface it.
    out = text(
        owner_comments=[
            comment(14, 6854, "BINDING NOW · ruling 190 · ops-b", t(timedelta(hours=-2)))
        ]
    )
    assert has(out, "ruling 190")


def test_the_48h_window_is_filtered_at_the_source_not_in_the_render():
    fake, _ = run_tick()
    # One #6854 read, already windowed by the snapshot: a lapsed record cannot reappear here.
    read = fake.asked("issues/6854/comments")
    assert read and f"since={snap.iso(NOW - snap.BINDING_LIFE)}" in read[0]


def test_the_roster_packages_and_map_are_read_from_origin_main_not_the_worktree():
    fake, _ = run_tick()
    for path in (tick.ROSTER, tick.MAP, tick.PKGS.format("ops")):
        assert ["git", "show", path] in fake.calls


# --- ruling 197: `for you:` lines from the machine footers -----------------------------------


def record(cid, body, footer=None, hours=-2):
    """A live #6854 record; ``footer`` is the bare field text after ``uplevel: ``."""
    tail = f"\n\n<!-- uplevel: {footer} -->" if footer else ""
    return comment(cid, 6854, body + tail, t(timedelta(hours=hours)))


def pointer(cid, number, footer, minutes=-1, prose="Pointer: read the review on line 2."):
    return comment(cid, number, f"{prose}\n\n<!-- uplevel: {footer} -->", t(timedelta(minutes=minutes)), pr=True)  # fmt: skip


def test_a_record_whose_footer_names_me_is_for_me_even_when_the_map_carries_it():
    # The original failure: ruling 177's filter hides every MAPPED ruling, so a record addressed to
    # a lane vanished from its digest the moment the map carried it. MAP carries ruling 188.
    out = text(owner_comments=[record(11, "BINDING NOW · ruling 188 · ops-b: keep going", "ruling=188 lanes=ops-b,backend packages=r157")])  # fmt: skip
    assert has(out, "for you: ruling 188 record 11 -> packages r157")
    assert not has(out, "not in the ruling map")  # the map filter itself is unchanged


def test_a_record_for_all_is_for_me_and_one_for_another_lane_is_not():
    out = text(
        owner_comments=[
            record(21, "BINDING NOW · ruling 189 · everyone", "ruling=189 lanes=all packages=none"),
            record(
                22, "BINDING NOW · ruling 190 · backend", "ruling=190 lanes=backend packages=r129"
            ),
        ]
    )
    assert has(out, "for you: ruling 189 record 21 -> packages none")
    assert not has(out, "record 22")
    # ...and the backend agent reads the other one, by the same footer
    be = text(
        owner_comments=[
            record(
                22, "BINDING NOW · ruling 190 · backend", "ruling=190 lanes=backend packages=r129"
            )
        ],
        sandbox="agent-uplevel-backend",
        beats=[coordinator(), heartbeat("agent-uplevel-backend", 3)],
    )
    assert has(be, "for you: ruling 190 record 22 -> packages r129")


def test_a_record_without_a_footer_prints_exactly_as_before():
    # Same record, with and without a footer naming someone else: byte-identical digests, so a
    # footer-less record (every record before ruling 197) changes nothing a lane reads.
    plain = record(12, "BINDING NOW · ruling 189 · ops-b: stop")
    other = record(12, "BINDING NOW · ruling 189 · ops-b: stop", "ruling=189 lanes=docs packages=none")  # fmt: skip
    assert text(owner_comments=[plain]) == text(owner_comments=[other])
    assert not has(text(owner_comments=[plain]), "for you")


def test_a_lapsed_record_is_not_for_anyone():
    # LIVE means the snapshot's own 48-hour BINDING_LIFE window; a footer does not extend a record.
    old = record(13, "BINDING NOW · ruling 150 · ops-b", "ruling=150 lanes=ops-b packages=none", hours=-49)  # fmt: skip
    assert not has(text(owner_comments=[old]), "for you")


def test_a_footer_is_read_only_from_the_last_line():
    body = "BINDING NOW · ruling 189\n<!-- uplevel: ruling=189 lanes=ops-b packages=none -->\nmore prose"
    assert tick.footer(body) is None
    # trailing blank lines and CRLF (GitHub returns either) do not hide it
    assert tick.footer("x\r\n\r\n<!-- uplevel: ruling=9 lanes=all packages=none -->\r\n\r\n")["ruling"] == 9  # fmt: skip


def test_a_malformed_footer_is_named_not_silently_dropped():
    bad = record(14, "BINDING NOW · ruling 189 · ops-b", "ruling=189 lanes=ops-b, docs packages=none")  # fmt: skip
    out = text(owner_comments=[bad])
    assert has(out, "NOTE unparsed uplevel footer on record 14")
    assert not has(out, "for you")


def test_the_pointer_window_is_my_beat_or_two_hours_back_capped_at_48():
    floor, cap = NOW - tick.POINTER_FLOOR, NOW - snap.BINDING_LIFE
    assert tick.pointer_window(NOW, None) == floor  # no beat: the floor
    assert tick.pointer_window(NOW, NOW - timedelta(minutes=3)) == floor  # fresh beat: the floor
    assert tick.pointer_window(NOW, NOW - timedelta(hours=5)) == NOW - timedelta(hours=5)  # stale
    assert tick.pointer_window(NOW, NOW - timedelta(hours=60)) == cap  # never past a record's life


def test_an_owner_pointer_on_my_pr_is_for_me():
    # The other original failure: a pointer reached the digest only as `1c/0r since beat`.
    out = text(repo_comments=[pointer(91, 7158, "pointer ruling=196 lane=ops-b")])
    assert has(out, "for you: owner pointer on #7158 (ruling 196) comment 91")


def test_the_pointer_read_is_one_repo_wide_call_from_the_window_start():
    # A 150-minute-old beat, so the window is the beat itself. The coordinator's read-through is
    # set 3 hours back so no snapshot read shares the URL: its comments read starts at the cursor,
    # and its activity read runs only for a beat older than the cursor.
    old_cursor = t(timedelta(hours=-3))
    beats = [
        heartbeat(
            "agent-uplevel-coordinator", 5, f"coordinator · tick\nread-through: {old_cursor}", cid=1
        ),
        heartbeat(SANDBOX, 150),
    ]
    fake, _ = run_tick(beats=beats)
    since = snap.iso(NOW - timedelta(minutes=150))
    assert fake.asked(f"repos/{REPO}/issues/comments?since={since}&per_page=100 --paginate") == [
        f"gh api repos/{REPO}/issues/comments?since={since}&per_page=100 --paginate"
    ]


def test_a_pointer_posted_before_my_beat_still_prints_inside_the_two_hour_floor():
    # Posted 90 minutes ago, my beat is 3 minutes old: a digest that read only "since my beat" lost
    # it for good the moment the agent beat once without acting on it.
    out = text(repo_comments=[pointer(92, 7158, "pointer ruling=196 lane=ops-b", minutes=-90)])
    assert has(out, "for you: owner pointer on #7158 (ruling 196) comment 92")


def test_a_stale_beat_widens_the_pointer_window_to_cover_what_it_slept_through():
    late = pointer(97, 7158, "pointer ruling=196 lane=ops-b", minutes=-240)
    assert has(text(repo_comments=[late], beat_min=300), "for you: owner pointer on #7158")
    # ...and a fresh beat does not re-read it: it printed on every tick of its first two hours
    assert not has(text(repo_comments=[late]), "for you")


@pytest.mark.parametrize("number", [7100, 7200])  # merged/closed (not open at all); another lane's
def test_a_pointer_on_a_pr_that_is_not_my_open_pr_still_prints(number):
    out = text(repo_comments=[pointer(93, number, "pointer ruling=196 lane=ops-b")])
    assert has(out, f"for you: owner pointer on #{number} (ruling 196) comment 93")


def test_a_pointer_for_another_lane_or_past_the_48_hour_cap_is_not_for_me():
    out = text(
        repo_comments=[
            pointer(94, 7158, "pointer ruling=196 lane=ops-a"),
            pointer(95, 7158, "pointer ruling=150 lane=ops-b", minutes=-50 * 60),
        ],
        beat_min=60 * 60,  # a 60-hour-old beat reaches back only 48 hours
    )
    assert not has(out, "for you")


def test_a_failed_pointer_read_says_so():
    fake = Fake(repo_comments=[pointer(96, 7158, "pointer ruling=196 lane=ops-b")], beat_min=300)
    fake.fail(f"issues/comments?since={snap.iso(NOW - timedelta(minutes=300))}")
    out = "\n".join(tick.build(fake, lambda: NOW, REPO, SANDBOX))
    assert has(out, "ERROR pointers:") and not has(out, "for you")


def test_the_for_you_lines_come_first_records_then_pointers():
    out = text(
        owner_comments=[
            record(31, "BINDING NOW · ruling 189", "ruling=189 lanes=ops-b packages=r181")
        ],
        repo_comments=[pointer(95, 7158, "pointer ruling=196 lane=ops-b")],
    )
    lines = out.splitlines()
    assert lines[1].startswith("  for you: ruling 189 record 31")
    assert lines[2].startswith("  for you: owner pointer on #7158")
    assert lines[3].startswith("  heartbeat id=")


def test_a_record_post_record_wrote_reaches_the_lanes_it_names_only(tmp_path, capsys):
    # The writer against this reader, end to end: post_record's dry-run body, served back as a live
    # #6854 comment, prints `for you:` for the lanes its footer names and for no other lane.
    src = tmp_path / "record.md"
    src.write_text("BINDING NOW · ruling 197: the digest's formats are checked\n\nBinds now.\n")
    args = ["record", "--ruling", "197", "--lanes", "heavy-a,ops-b", "--packages", "r197"]
    assert post.main([*args, "--body-file", str(src), "--dry-run"], run=None) == 0
    body = capsys.readouterr().out.rstrip("\n")
    owner = [comment(6198161166, 6854, body, t(timedelta(hours=-1)))]
    assert has(text(owner_comments=owner), "for you: ruling 197 record 6198161166 -> packages r197")
    backend = text(
        owner_comments=owner,
        sandbox="agent-uplevel-backend",
        beats=[coordinator(), heartbeat("agent-uplevel-backend", 3)],
    )
    assert not has(backend, "for you")


# --- ruling 197: --beat writes the heartbeat ------------------------------------------------


def beat(text_, **over):
    fake = Fake(**over)
    sandbox = over.get("sandbox", SANDBOX)
    code = tick.main(["--sandbox", sandbox, "--repo", REPO, "--beat", text_], run=fake, clock=lambda: NOW)  # fmt: skip
    return code, fake, [c for c in fake.calls if c[:3] == ["gh", "api", "-X"]]


def test_beat_patches_my_comment_with_the_marker_the_tool_writes(capsys):
    code, fake, writes = beat("ops-b · 09:30Z · working #7164")
    assert code == 0
    assert writes == [
        ["gh", "api", "-X", "PATCH", f"repos/{REPO}/issues/comments/{BEAT_ID}",
         "-f", f"body=<!-- heartbeat:{SANDBOX} -->\nops-b · 09:30Z · working #7164"],
    ]  # fmt: skip
    # one read to find the comment, one write -- the digest's reads are not paid for a beat
    assert len(fake.calls) == 2
    assert capsys.readouterr().out.strip().startswith(f"beat written: comment {BEAT_ID} on #6958")


def test_beat_finds_my_comment_under_the_other_spelling_and_writes_the_one_i_passed():
    _, _, writes = beat("x", beats=[coordinator(), heartbeat("uplevel-ops-b", 3)])
    assert writes[0][4] == f"repos/{REPO}/issues/comments/{BEAT_ID}"
    assert writes[0][-1].startswith(f"body=<!-- heartbeat:{SANDBOX} -->\n")


def test_beat_with_no_comment_yet_posts_one(capsys):
    code, _, writes = beat("ops-b · 09:30Z · idle", beats=[coordinator()])
    assert code == 0
    assert writes == [
        ["gh", "api", "-X", "POST", f"repos/{REPO}/issues/6958/comments",
         "-f", f"body=<!-- heartbeat:{SANDBOX} -->\nops-b · 09:30Z · idle"],
    ]  # fmt: skip
    assert f"beat posted: new comment {NEW_BEAT_ID}" in capsys.readouterr().out


def test_beat_over_ur155s_600_characters_is_refused_before_any_call(capsys):
    marker = len(tick.beat_body(SANDBOX, ""))
    code, fake, _ = beat("x" * (tick.BEAT_CAP - marker + 1))
    assert code == 2 and fake.calls == []
    assert "601 characters" in capsys.readouterr().err
    # the boundary itself is allowed: the cap is "at most 600", marker line included
    code, _, writes = beat("x" * (tick.BEAT_CAP - marker))
    assert code == 0 and len(writes[0][-1]) == len("body=") + tick.BEAT_CAP


def test_beat_text_carrying_its_own_marker_is_refused(capsys):
    code, fake, _ = beat(f"<!-- heartbeat:{SANDBOX} -->\nops-b · 09:30Z · idle")
    assert code == 2 and fake.calls == []
    assert "marker" in capsys.readouterr().err


@pytest.mark.parametrize("sandbox", ["agent-uplevel-coordinator", "uplevel-coordinator"])
def test_beat_refuses_the_coordinator_whose_beat_carries_its_read_through(sandbox, capsys):
    # The coordinator's heartbeat holds the `read-through:` cursor every tick reads from; a
    # two-line beat written over it would erase that cursor (roles/coordinator.md owns it).
    code, fake, _ = beat("coordinator · 09:30Z · tick", sandbox=sandbox)
    assert code == 2 and fake.calls == []
    assert "read-through" in capsys.readouterr().err


def test_beat_after_a_failed_read_writes_nothing(capsys):
    # "No beat found" from a read that never happened would POST a duplicate row.
    fake = Fake()
    fake.fail("/issues/6958/comments")
    code = tick.main(["--sandbox", SANDBOX, "--repo", REPO, "--beat", "x"], run=fake, clock=lambda: NOW)  # fmt: skip
    assert code == 1
    assert not [c for c in fake.calls if "-X" in c]
    assert "ERROR heartbeats" in capsys.readouterr().err


# --- my PR's gate ---------------------------------------------------------------------------


def ready(rollup=None, labels=("lane:ops", "cell:b"), armed=False, draft=False):
    """#7158 -- mine, on OTHER_BRANCH -- alone, in the shape a marker test varies. Its default
    rollup is a READY run: the green gate plus a job of the same run that really ran."""
    rollup = rollup if rollup is not None else [gate(), job()]
    p = pr(7158, labels=list(labels), head=MINE2_HEAD, draft=draft, rollup=rollup, title=MINE2, armed=armed)  # fmt: skip
    return {"prs": [p], "heads": [head_row(7158, OTHER_BRANCH, MINE2)]}


def test_an_in_flight_gate_names_the_jobs_still_running():
    out = text(
        **ready(rollup=[gate(None, "IN_PROGRESS")]),
        jobs=[
            {"name": "Feature check (fake AI)", "status": "in_progress"},
            {"name": "CI Gate (Required Checks)", "status": "in_progress"},
        ],
    )
    line = row(out, 7158)
    assert "IN_PROGRESS(Feature check (fake AI))" in line
    # The gate is a leg of its own run: naming it "still running" would say the thing we
    # are waiting on is the thing that is waiting.
    assert "CI Gate (Required Checks))" not in line


def test_a_gate_that_already_resolved_pays_no_job_read():
    fake, _ = run_tick()
    assert fake.asked("/jobs") == []


def test_a_gate_beyond_the_list_apis_100_row_cap_is_re_read_before_it_prints():
    # The batch caps each PR's rollup at 100 rows, which is how a green gate once printed as absent.
    # The digest must print the RE-READ verdict, not the truncated batch's.
    capped = [filler() for _ in range(snap.LIST_ROLLUP_CAP - 1)] + [gate("FAILURE")]
    fake, out = run_tick(**ready(rollup=capped), rollup_reread={7158: [gate("SUCCESS")]})
    assert fake.asked("gh pr view 7158")
    assert "gate=SUCCESS" in row(out, 7158)


# --- ruling 198: `needs your review` and `arm auto-merge` on my own PRs ----------------------
# The markers read reviews as the coordinator's tick and merge audit do: REVIEWS_JQ's comments,
# `is_approval` on the first line, and `Snapshot.judge` (the sha named, else the UR-106 carry).
# Nothing is ever judged by date: a review naming no sha says so, an unread carry says so.


def review(cid, body=APPROVE, minutes=-10):
    """A comment on #7158, posted ``minutes`` ago (the time decides nothing; the sha does)."""
    return comment(cid, 7158, body, t(timedelta(minutes=minutes)), pr=True)


def approve_of(rev):
    """The default approval, naming ``rev`` instead of the head on its first line."""
    return APPROVE.replace(MINE2_HEAD[:9], rev[:9])


NO_SHA = APPROVE.replace(f" `{MINE2_HEAD[:9]}`", "")


def marked(**over) -> str:
    return row(text(**over), 7158)


def test_a_ready_pr_with_a_finished_real_run_and_no_review_needs_my_review():
    assert "— needs your review" in marked(**ready())
    # a red gate is finished too: the review reads the failing run (ruling 161), it does not wait
    assert "— needs your review" in marked(**ready(rollup=[gate("FAILURE"), job()]))


def test_an_approve_naming_the_head_with_plan_text_none_and_a_real_green_run_arms_auto_merge():
    fake, out = run_tick(**ready(), pr_comments={7158: [review(45)]})
    assert row(out, 7158).endswith("— arm auto-merge")
    # identity: the approval names the head, so no UR-106 diff is read
    assert not fake.asked("--json files")
    # the reviews are the snapshot's own verdict read, filter and all
    assert fake.asked(f"issues/7158/comments?per_page=100 --paginate --jq {snap.REVIEWS_JQ}")


def test_a_self_review_heading_is_no_approval_as_the_audit_reads_it():
    # Reproduction (a): the merge audit keys on the FIRST line (REVIEWS_JQ, is_approval) and reads
    # this as "no approving review", so arming it would merge what the audit then flags.
    body = f"## Self-review\n**Review: approve** `{MINE2_HEAD[:9]}`\n- **Plan text:** none.\n"
    line = marked(**ready(), pr_comments={7158: [review(44, body)]})
    assert "arm auto-merge" not in line
    assert "— needs your review" in line  # no review the coordinator counts: still owed


def test_an_approve_of_an_old_head_the_author_changed_is_not_for_this_head():
    # Reproduction (b): it names OLD_HEAD and the author's later commit changed the own diff, so
    # UR-106 says no carry -- however recently it was posted.
    fake, out = run_tick(
        **ready(),
        pr_comments={7158: [review(46, approve_of(OLD_HEAD), minutes=-1)]},
        diffs={OLD_HEAD[:9]: SAME_DIFF.replace("+b", "+c")},
    )
    line = row(out, 7158)
    assert "arm auto-merge" not in line and "— needs your review" in line
    assert fake.asked("--json files")  # the carry was read, the judge's way


def test_an_update_branch_head_the_approval_carries_needs_no_new_review():
    # Reproduction (c): the coordinator's update-branch made a new head whose own diff equals the
    # approved one (UR-106 carry). The approval still holds, so no re-review is owed.
    line = marked(
        **ready(),
        pr_comments={7158: [review(47, approve_of(OLD_HEAD), minutes=-40)]},
        diffs={},  # same diff at both revs: the carry
    )
    assert "needs your review" not in line
    assert line.endswith("— arm auto-merge")


def test_a_reply_quoting_a_verdict_is_not_a_review():
    # Reproduction (d): a quote starts with `>`, so REVIEWS_JQ (body starts `Review:`) skips it,
    # as the coordinator does; it must not stand in for the review the PR still needs.
    body = "> Review: changes requested\n\nFixed in the next push.\n"
    line = marked(**ready(), pr_comments={7158: [review(48, body)]})
    assert "— needs your review" in line


def test_a_changes_requested_review_of_the_head_is_a_review_and_arms_nothing():
    body = f"Review: changes requested `{MINE2_HEAD[:9]}`\nPlan text: none\n"
    line = marked(**ready(), pr_comments={7158: [review(49, approve_of(MINE2_HEAD), minutes=-20), review(50, body, minutes=-5)]})  # fmt: skip
    assert "needs your review" not in line and "arm auto-merge" not in line


@pytest.mark.parametrize("minutes", [-1, -40])  # posted after or before the head commit: same
def test_a_review_naming_no_head_says_so_and_is_never_armed_by_date(minutes):
    # The review form puts the reviewed head's sha on the first line; without it the judge cannot
    # tell which head was reviewed, and no date may stand in for it. The author re-posts with it.
    fake, out = run_tick(**ready(), pr_comments={7158: [review(51, NO_SHA, minutes=minutes)]})
    line = row(out, 7158)
    assert line.endswith("— review names no head")
    assert "arm auto-merge" not in line and "needs your review" not in line
    assert not fake.asked("git log -1")  # no head-date read exists any more
    # also when the newest review is a changes-requested one naming no sha
    body = "Review: changes requested\nPlan text: none\n"
    assert marked(**ready(), pr_comments={7158: [review(52, body)]}).endswith("— review names no head")  # fmt: skip


def test_an_old_sha_approval_whose_carry_read_fails_is_unread_never_armed():
    # The reviewer's case: the approval names OLD_HEAD, the carry would be false, and the PR's
    # files read answers 502. Nothing was judged, so nothing is armed and the row says so.
    fake = Fake(**ready(), pr_comments={7158: [review(53, approve_of(OLD_HEAD), minutes=-1)]}, diffs={OLD_HEAD[:9]: "different\n"})  # fmt: skip
    fake.fail("--json files")
    out = "\n".join(tick.build(fake, lambda: NOW, REPO, SANDBOX))
    line = row(out, 7158)
    assert "— review unread" in line
    assert "arm auto-merge" not in line and "needs your review" not in line
    assert "ERROR own-diff files of #7158" in line  # the cause, on the row the snapshot's way


@pytest.mark.parametrize(
    ("why", "case"),
    [
        ("a draft is not reviewed", dict(ready(draft=True))),
        ("CI still running at the head", dict(ready(rollup=[gate(None, "IN_PROGRESS"), job()]))),
        ("CI queued", dict(ready(rollup=[gate(None, "QUEUED"), job()]))),
        ("no gate at the head at all", dict(ready(rollup=[filler()]))),
        ("an approve at the head exists", {**ready(), "pr_comments": {7158: [review(54)]}}),
        # item 6: a draft run's all-skipped SUCCESS is not a finished run
        ("the gate's run was a draft run", dict(ready(rollup=[gate(), job("SKIPPED")]))),
        ("the gate's run ran nothing but the gate", dict(ready(rollup=[gate()]))),
    ],
)
def test_needs_your_review_is_not_printed_when(why, case):
    assert "needs your review" not in marked(**case), why


def test_a_draft_run_prints_neither_marker():
    for comments in ([], [review(55)]):
        line = marked(**ready(rollup=[gate(), job("SKIPPED")]), pr_comments={7158: comments})
        assert "needs your review" not in line and "arm auto-merge" not in line, line


@pytest.mark.parametrize(
    ("why", "case"),
    [
        (
            "the newest review requests changes",
            {
                **ready(),
                "pr_comments": {
                    7158: [
                        review(56, minutes=-20),
                        review(57, f"Review: changes requested `{MINE2_HEAD[:9]}`\n", minutes=-5),
                    ]
                },
            },
        ),
        (
            "Plan text names an owner kind",
            {
                **ready(),
                "pr_comments": {
                    7158: [review(58, APPROVE.replace("none.", "rule text (UR-47 owner kind)."))]
                },
            },
        ),
        (
            "the review states no Plan text",
            {
                **ready(),
                "pr_comments": {
                    7158: [review(59, f"Review: approve `{MINE2_HEAD[:9]}`\nNotes:\n")]
                },
            },
        ),
        (
            "the owner label",
            {**ready(labels=("lane:ops", "owner")), "pr_comments": {7158: [review(60)]}},
        ),
        ("auto-merge already on", {**ready(armed=True), "pr_comments": {7158: [review(61)]}}),
        (
            "the gate is red",
            {**ready(rollup=[gate("FAILURE"), job()]), "pr_comments": {7158: [review(62)]}},
        ),
        (
            "CI still running",
            {
                **ready(rollup=[gate(None, "IN_PROGRESS"), job()]),
                "pr_comments": {7158: [review(63)]},
            },
        ),
        ("a draft", {**ready(draft=True), "pr_comments": {7158: [review(64)]}}),
        (
            "the gate's run was a draft run (every job skipped)",
            {**ready(rollup=[gate(), job("SKIPPED")]), "pr_comments": {7158: [review(65)]}},
        ),
        (
            "the gate's run ran nothing but the gate",
            {**ready(rollup=[gate()]), "pr_comments": {7158: [review(66)]}},
        ),
        (
            "the only real job belongs to another run",
            {
                **ready(rollup=[gate(), job("SKIPPED"), filler()]),
                "pr_comments": {7158: [review(67)]},
            },
        ),
        ("the approval names no head", {**ready(), "pr_comments": {7158: [review(68, NO_SHA)]}}),
    ],
)
def test_arm_auto_merge_is_not_printed_when(why, case):
    assert "arm auto-merge" not in marked(**case), why


def test_a_real_run_is_one_whose_own_non_gate_check_succeeded():
    assert tick.ran_for_real([gate(), job("SKIPPED"), job("SUCCESS", name="Lint")], GATE_RUN)
    assert not tick.ran_for_real([gate(), job("SKIPPED")], GATE_RUN)
    assert not tick.ran_for_real([gate(), filler()], GATE_RUN)  # run 901, not the gate's
    assert not tick.ran_for_real([gate(), job()], None)


def test_a_draft_pays_no_marker_read():
    fake, _ = run_tick(**ready(draft=True))
    assert not fake.asked("--jq") and not fake.asked("--json files")


def test_an_unread_review_read_says_review_unread_never_nothing():
    fake = Fake(**ready())
    fake.fail("issues/7158/comments?per_page")
    out = "\n".join(tick.build(fake, lambda: NOW, REPO, SANDBOX))
    assert "— review unread" in row(out, 7158)
    assert has(out, "ERROR review comments #7158:")


# --- my own open PRs ------------------------------------------------------------------------


def test_my_open_prs_are_derived_from_my_branches():
    # Labels carry cell:a on ops-a's PRs and no cell at all on some of mine, and the author login is
    # the owner's for every PR (UR-168): the branch set is the only ownership fact that always holds.
    out = text()
    assert has(out, "== mine (2)") and has(out, "#7164") and has(out, "#7158")


def test_a_pr_on_a_branch_i_do_not_hold_is_not_mine():
    out = text(
        heads=[
            head_row(7158, THEIRS),
            head_row(7164, THEIRS),
            head_row(7200, THEIRS),
        ]
    )
    assert has(out, "== mine (0)")


def test_behind_counts_commits_main_has_that_my_head_lacks():
    fake, out = run_tick()
    assert "behind 3" in row(out, 7158)
    ranges = [c for c in fake.calls if c[:2] == ["git", "rev-list"]]
    # The reversed range counts MY work ahead of main -- a different number, and the wrong one for
    # "do I need to rebase".
    assert ranges[0][-1] == "refs/remotes/origin/pr/7158..origin/main"


def test_dirty_is_flagged_on_my_rows():
    assert "DIRTY" in row(text(), 7158)


def test_comments_and_reviews_since_my_beat_are_counted_on_each_of_my_prs():
    _, out = run_tick(
        pr_comments={
            7158: [
                comment(81, 7158, "Reviewer lane: backend\nflag: rename", t(timedelta(minutes=-1)))
            ]
        },
        pr_reviews={
            7158: [{"submitted_at": t(timedelta(minutes=-2)), "body": "Review: request changes"}]
        },
    )
    assert "1c/1r since beat" in row(out, 7158)


def test_activity_older_than_my_beat_is_not_counted():
    _, out = run_tick(
        pr_comments={
            7158: [comment(82, 7158, "Reviewer lane: backend\nold flag", t(timedelta(hours=-3)))]
        }
    )
    assert "0c/0r since beat" in row(out, 7158)


def test_the_since_watermark_is_my_beats_updated_at():
    fake, _ = run_tick()
    read = [c for c in fake.asked("issues/7158/comments") if "since=" in c]
    assert read and f"since={BEAT_AT}" in read[0]


# --- the next claimable package -------------------------------------------------------------


def test_a_queue_entry_is_the_token_that_LEADS_it_not_every_backticked_word():
    # Both rows below are main's roster VERBATIM. ops-b's F2.3 entry says "after `[r157]`'s runner is
    # ready for the owner" -- a cross-reference -- and heavy-b's says "`B2.3` once `O2.4` passes".
    # A findall over the cell made each reference a queue slot: the live digest then printed
    # `holding open claim: [r157], [r157]`, and heavy-b would have been OFFERED `O2.4`, another
    # lane's package. Prose can name anything, so only a token that STARTS an entry is a slot.
    ops_b = (
        "`[r157]`, `[r141]` follow-up (ruling 145), `[r151]`, `F2.3` UI (OP-3, after `[r157]`'s "
        "runner is ready for the owner), `[r181]`, `[r172]`, `O3.4`; `OB.4` on its trigger"
    )
    assert tick.queue_entries(ops_b) == [
        "r157",
        "r141",
        "r151",
        "F2.3",
        "r181",
        "r172",
        "O3.4",
        "OB.4",
    ]
    heavy_b = (  # fmt: skip
        "`F2.3` UI OP-1's `unverified` rows (ruling 184), then F2.3's seeded CI project (ruling 187); "
        "assigned `heavy` PRs labelled `cell:heavy-b`: `B2.3` once `O2.4` passes"
    )
    got = tick.queue_entries(heavy_b)
    assert "O2.4" not in got and "heavy" not in got and "unverified" not in got  # fmt: skip
    assert got == ["F2.3"]  # the clause-leading entry leads with prose, so it is prose, not a slot
    # The safe direction of the two: prose mid-entry can only OMIT a slot, never INVENT one. An
    # invented slot is the one that does damage -- it gets offered to me to claim. The fixture's
    # clean queue order is pinned by test_my_roster_queue_is_the_order_...
    #
    # The paren-depth guard is what separates a comma that SEPARATES entries from one that separates
    # prose -- and unlike the case just above (" after `[r157]`", which the leading-token rule rejects
    # by itself), this fragment BEGINS with the backtick, so only the depth check can tell it is
    # prose. No cell on main reads this way today (measured); it is the shape the guard is for.
    nested = "`F2.3` UI (OP-3, `[r157]` first, then `[r172]`), `[r181]`"
    assert tick.queue_entries(nested) == ["F2.3", "r181"]


def test_the_next_claimable_package_follows_MY_roster_queue_not_the_files_order():
    # ops.md carries ops-a's [r164a] with `**PR:** none yet` physically BEFORE my [r181], so a scan
    # in file order offers another cell's package -- and offering it is a claim on someone else's
    # queue. The roster queue is the order.
    out = text(
        prs=[
            pr(7164, labels=["lane:ops", "cell:b"], head=MY_HEAD, title="an [r151] follow-up"),
        ],
        heads=[head_row(7164, MY_BRANCH, "an [r151] follow-up")],
    )
    assert "next claimable: r181" in out  # fmt: skip


def test_holding_a_package_on_my_queue_offers_no_claim_and_says_why():
    # UR-52: "on any tick where it has no open package". The default scenario is the live one -- an
    # open PR titles [r181], which sits on my queue -- so the digest must NOT offer a fresh claim.
    # It was the bug this box fixes: the old pin here asserted `next claimable: r172` while [r181]
    # was open, i.e. it pinned the invitation to queue-jump. Silence would be no better: it could
    # mean "nothing left claimable" or "not eligible", and a lane cannot act on the difference.
    out = text()
    assert "holding open claim: [r181]" in out
    assert "UR-52" in has(out, "holding open claim")[0]
    assert "next claimable" not in out


def test_a_ur_nn_defect_fix_gates_nothing_and_the_queue_is_still_offered():
    # The other side of the same rule, and the control that the gate above is not a blanket refusal.
    # A `[UR-nn]` fix has no package number (UR-48: a lane defect needs no package), so it occupies
    # no queue slot -- it is NOT an open package and must not freeze the queue. That is this very
    # sandbox's shape for hours: uplevel/lane-panel-recommendation-leg, titled `[UR-48] fix: ...`.
    defect = pr(7151, labels=["lane:ops"], head=MY_HEAD, title="[UR-48] fix: re-anchor a panel leg")
    out = text(
        prs=[defect],
        heads=[head_row(7151, MY_BRANCH, "[UR-48] fix: re-anchor a panel leg")],
    )
    assert "holding open claim" not in out
    assert "next claimable: r181" in out


def test_a_package_whose_pr_field_names_one_of_my_prs_is_held_by_that_reason_too():
    # Two independent readings, because they disagree in both directions. Here the title names
    # nothing on my queue, but [r172]'s block carries `**PR:** #7164` and #7164 is mine: an
    # acknowledged claim with an un-reflective title. The digest still has to say the state.
    pkg = PKG.replace("none yet. (ruling 172", "#7164. (ruling 172")
    out = text(
        packages=pkg,
        prs=[pr(7164, labels=["lane:ops", "cell:b"], head=MY_HEAD, title="an unrelated title")],
        heads=[head_row(7164, MY_BRANCH, "an unrelated title")],
    )
    assert "holding open claim: [r172]" in out
    assert "next claimable" not in out


def test_a_package_whose_pr_field_wrapped_to_the_next_line_is_still_read():
    # [r172]'s header on main wraps: `**PR:**` ends the line, `none yet.` opens the next. A
    # line-local scan never sees the value and reports the package as already claimed.
    assert tick.next_claimable(PKG, ["r172"], []) == "r172"


def test_a_package_already_titled_by_one_of_my_prs_is_skipped():
    assert tick.next_claimable(PKG, ["r172"], [{"title": "[r172] import budget"}]) is None


def test_a_queue_token_with_no_block_in_the_file_is_skipped():
    assert tick.next_claimable(PKG, ["F2.3", "O3.4", "r172"], []) == "r172"


def test_a_package_that_names_a_pr_is_not_offered():
    assert tick.next_claimable(PKG, ["r157", "r172"], []) == "r172"


def test_held_claims_reads_a_hold_from_the_title_and_from_the_pr_field():
    mine = [{"number": 7164, "title": "[r181] the lane-tick digest"}]
    assert tick.held_claims(PKG, mine) == ["r181"]
    # by the field alone (the title names nothing here, `**PR:**` on [r172] names my #7164)
    field = PKG.replace("none yet. (ruling 172", "#7164. (ruling 172")
    assert tick.held_claims(field, [{"number": 7164, "title": "nothing here"}]) == ["r172"]  # fmt: skip
    # neither: a [UR-nn] fix titles no package and no field names one (UR-48: gates nothing)
    assert tick.held_claims(PKG, []) == []
    assert tick.held_claims(PKG, [{"number": 7151, "title": "[UR-48] fix: a leg"}]) == []


def test_a_hold_the_roster_queue_never_names_still_closes_the_claim_leg():
    # ops-a's shape on live `main`, and the reason the scan walks the FILE and not the queue:
    # `ops.md`'s own `### [r162]` field reads `**PR:** #7114 (open)` and the open PR titles
    # `[r162]`, yet `roles/lane.md:23`'s ops-a column carries no `[r162]` token. A queue-driven
    # scan answered "no holds" and the digest printed `next claimable: r164a` mid-flight -- the
    # queue-jump UR-52 forbids. Reviewer ops-a reproduced it live at 11:21Z.
    ops_a = PKG + (
        "### [r162] The engine socket follows the orchestrator setting\n\n"
        "**Flags:** owner. **Assigned:** `uplevel-ops-a`. **PR:** #7114 (open). (ruling 162)\n"
    )
    mine = [{"number": 7114, "title": "[r162] claim: engine socket follows the orchestrator"}]
    assert tick.held_claims(ops_a, mine) == ["r162"]
    # both readings hold it on their own, since the two sources can each be the only live one
    assert tick.held_claims(ops_a, [{"number": 7114, "title": "[r162] anything"}]) == ["r162"]
    assert tick.held_claims(ops_a, [{"number": 7114, "title": "no token here"}]) == ["r162"]
    # and the offer the gate must suppress genuinely IS there -- a gate that suppressed an offer
    # that was never produced would pass this file without protecting anything.
    assert tick.next_claimable(ops_a, ["F2.3", "r164a", "O2.5"], mine) == "r164a"


def test_a_none_yet_field_naming_an_issue_or_a_closed_pr_is_not_a_hold():
    # The widened scan reads every block, so a `**PR:** none yet` field that merely CITES a number
    # must not become a hold. main's real shapes: ops `[r172]` cites `issue #7102`, and frontend
    # `[r160a]`/backend `[r160b]` cite CLOSED dependabot PRs -- measured 1 such field per file.
    assert tick.held_claims(PKG, [{"number": 7102, "title": "an issue, not a claim"}]) == []
    dependabot = PKG + (
        "### [r160a] Deferred npm majors\n\n"
        "**Flags:** none. **Assigned:** `uplevel-frontend`.\n**PR:** none yet.\n"
        "(ruling 160; dependabot #7058, #7059, #7060, closed with `@dependabot ignore`)\n"
    )
    assert tick.held_claims(dependabot, [{"number": 7058, "title": "bump vite"}]) == []
    # positive control: the SAME block with the disclaimer removed is a field-hold, so the arm
    # above passes by honouring `none yet` and not by failing to find the number at all.
    claimed = dependabot.replace("**PR:** none yet.\n", "**PR:** #7058 (open).\n")
    assert tick.held_claims(claimed, [{"number": 7058, "title": "bump vite"}]) == ["r160a"]


def test_a_hold_and_a_claimable_are_never_both_printed():
    # The branch order in `build` is the rule: the hold wins and the offer is suppressed, so a lane
    # never reads a package it may claim from a digest that also says it is mid-flight.
    mine = [{"number": 7164, "title": "[r181] the lane-tick digest"}]
    assert tick.held_claims(PKG, mine) == ["r181"]
    assert tick.next_claimable(PKG, ["r181", "r172"], mine) == "r172"  # the offer EXISTS...
    out = text()
    assert "next claimable" not in out  # ...and is the line the gate suppresses.


# --- the error shape the package names ------------------------------------------------------


@pytest.mark.parametrize(
    ("needle", "section"),
    [
        ("df -h", "disk"),
        # #6958's comments are BOTH the read-through cursor and the heartbeat rows, so one failure
        # legitimately reports under two tags; the beat is the one the tick cannot act without.
        ("/issues/6958/comments", "heartbeats"),
        ("/issues/6854/comments", "binding_now"),
        ("headRefName", "heads"),
        ("git branch", "branches"),
        ("rev-list", "behind #7158"),
        # ruling 198's verdict read on my ready #7158: unread, never "no marker owed"
        ("issues/7158/comments?per_page", "review comments #7158"),
        ("roles/lane.md", "identities"),
        ("packages/ops.md", "packages"),
        ("ruling-map.md", "ruling map"),
    ],
)
def test_a_failing_call_prints_error_for_its_named_section_never_an_empty_one(needle, section):
    # The section NAME is asserted, not just that some ERROR appeared: a report that prints the
    # right number of errors under renamed tags would pass a bare `assert errs`, and UR-29 is about
    # the lane knowing WHICH reading it is missing.
    fake = Fake()
    fake.fail(needle)
    out = "\n".join(tick.build(fake, lambda: NOW, REPO, SANDBOX))
    errs = has(out, "ERROR")
    assert errs, f"{needle} failed silently"
    named = [ln for ln in errs if ln.strip().startswith(f"ERROR {section}:")]
    assert named, f"no error named {section}; printed: {[ln.strip() for ln in errs]}"
    # The CAUSE must be among them. #6958's comments feed two sections, so a broken read there
    # legitimately yields the 502 plus a derived "no beat" line -- both under one tag, and a pin
    # that read only the first would fail for the wrong reason.
    assert any("HTTP 502" in ln for ln in named), [ln.strip() for ln in named]


def test_a_lane_with_no_package_file_notes_it_rather_than_erroring():
    # main carries package files for backend/docs/frontend/ops ONLY; the roster's heavy and operator
    # rows have work that is never packaged. Those are exactly the roles box 3 points at this tool,
    # so a missing file is a fact to state, not a broken read -- an ERROR on the operator's own tick
    # would be a false alarm every 30 minutes. The claim still comes from the roster row, printed
    # above, so the lane loses nothing but a redundant confirmation.
    out = text(sandbox="uplevel-heavy-b", beats=[heartbeat("uplevel-heavy-b", 3)])
    assert has(out, "NOTE no package file for lane heavy")
    assert not has(out, "ERROR packages")
    # Asked positively: the existence check is ls-tree, not a git show whose failure could not say
    # WHY it failed (a missing file and a network fault both arrive as exit 128).
    fake, _ = run_tick(sandbox="uplevel-heavy-b", beats=[heartbeat("uplevel-heavy-b", 3)])
    assert fake.asked("git ls-tree origin/main -- :/docs/uplevel/packages/heavy.md")


def test_one_failing_section_never_takes_the_report_down():
    fake = Fake()
    fake.fail("df -h")
    out = "\n".join(tick.build(fake, lambda: NOW, REPO, SANDBOX))
    assert has(out, "ERROR disk") and has(out, "#7158") and has(out, "#7164")


def test_a_failing_behind_count_is_named_on_the_row_and_reported():
    fake = Fake()
    fake.fail("rev-list")
    out = "\n".join(tick.build(fake, lambda: NOW, REPO, SANDBOX))
    assert "behind ?" in row(out, 7158)
    assert has(out, "ERROR behind #7158")


def test_a_failing_roster_read_leaves_the_report_at_one_error_line():
    fake = Fake()
    fake.fail("roles/lane.md")
    out = "\n".join(tick.build(fake, lambda: NOW, REPO, SANDBOX))
    # One failure, one line: the read that broke speaks for itself once, and a second line naming
    # the same cause under another name invites two different fixes for one problem.
    assert len(out.splitlines()) == 1 and out.startswith("ERROR identities:")
    assert "HTTP 502" in out  # the reason survives, not just the section name


# --- the properties the package names -------------------------------------------------------


def test_the_tool_is_read_only():
    fake, _ = run_tick()
    for cmd in fake.calls:
        assert "-X" not in cmd and "--method" not in cmd, cmd
        if cmd[0] == "gh":
            assert (cmd[1], cmd[2] if cmd[1] == "pr" else "") in (
                ("pr", "list"),
                ("pr", "view"),
                ("api", ""),
            ), cmd
        else:
            assert cmd[0] in ("git", "df"), cmd
            assert cmd[1] in (
                "show",
                "ls-tree",
                "branch",
                "rev-list",
                "merge-base",
                "fetch",
                "log",
                "-h",
            ), cmd


def test_a_lane_tick_fits_the_tools_own_line_cap():
    # ops.md:493 caps this tool "at most 80 lines". No scripts/uplevel script is 80 SOURCE lines
    # (the shortest is 250; the snapshot it drives is 1,200), and the only size rule the programme
    # carries is an OUTPUT bound -- status_draft's LIMIT reports the excess, it does not truncate.
    # So the cap reads on the printed digest, and overrunning it reports itself rather than cutting
    # a section off. ops-a can overrule the reading; the pin moves with the ruling.
    assert len(text().splitlines()) <= tick.CAP_LINES


def test_an_over_cap_digest_reports_its_own_overflow_and_cuts_nothing():
    # The other half of the cap reading (the test above pins the under-cap default). "at most 80
    # lines" is a bound we pay with a REPORT, not a truncation: cutting a section to fit would
    # silently delete a PR row or a BINDING NOW record, which is the UR-29 failure this tool exists
    # to prevent. So a long PR section must print every row AND name the excess.
    # Measured growth: one line per PR row on an 11-line default, so 80 rows puts the digest past
    # the cap. The number is checked against the printed output, not against the expression that
    # produced it -- and it excludes the NOTE itself, which is the shape worth pinning. The rows are
    # my own draft PRs (ruling 198 left no other PR section), so each costs its row's reads only.
    n = tick.CAP_LINES
    many = [pr(7300 + i, labels=["lane:ops"], head=MY_HEAD, title=f"leg {i}") for i in range(n)]
    heads = [head_row(7300 + i, MY_BRANCH, f"leg {i}") for i in range(n)]
    lines = text(prs=many, heads=heads).splitlines()
    note = [ln for ln in lines if "lines over" in ln]
    assert len(note) == 1
    excess = int(note[0].split()[1])
    assert excess > 0 and excess == len(lines) - 1 - n
    assert len(has("\n".join(lines), "leg 79")) == 1  # the LAST row survives: it reports, not cuts
    assert f"== mine ({n})" in "\n".join(lines)


def test_the_digest_stays_under_the_programmes_character_bound():
    # status_draft keeps a coordinator's whole status under this; a lane's reading is a subset.
    assert len(text()) <= status.LIMIT
