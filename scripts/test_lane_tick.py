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


def coordinator(minutes=5):
    return heartbeat(
        "agent-uplevel-coordinator",
        minutes,
        f"coordinator · 09:2xZ · tick\nread-through: {CURSOR}",
        cid=1,
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


def pr(number, *, labels, head, draft=True, merge="BEHIND", rollup=None, title="pr"):
    """A row of the snapshot's batched ``gh pr list`` (the verdict-carrying read)."""
    return {
        "number": number,
        "title": title,
        "isDraft": draft,
        "labels": [{"name": n} for n in labels],
        "headRefOid": head,
        "mergeStateStatus": merge,
        "autoMergeRequest": None,
        "statusCheckRollup": rollup if rollup is not None else [gate()],
    }


def head_row(number, branch, body, title="pr"):
    """A row of the digest's OWN ``gh pr list`` -- the one that asks for headRefName and body."""
    return {"number": number, "title": title, "headRefName": branch, "body": body}


MINE2 = "[r151] soft-deleted defect events"
MINE1 = "[r181] the lane-tick digest"
NOTMINE = "theirs"
GREEN_PRS = [
    pr(7158, labels=["lane:ops", "cell:b"], head=MINE2_HEAD, draft=False, merge="DIRTY", title=MINE2),
    pr(7164, labels=["lane:ops", "cell:b"], head=MY_HEAD, title=MINE1),
    pr(7200, labels=["lane:backend", "review:ops-b"], head=THEIRS_HEAD, draft=False, title=NOTMINE),
]  # fmt: skip
GREEN_HEADS = [
    head_row(7158, OTHER_BRANCH, PLAN := "# x\n\n- **Plan text:** none.\n", MINE2),
    head_row(7164, MY_BRANCH, PLAN, MINE1),
    head_row(7200, THEIRS, "# x\n\n## Body\nno such line\n", NOTMINE),
]  # fmt: skip

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
        self.reviews = over.get("reviews", [])
        self.pr_comments = over.get("pr_comments", {})
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
        if cmd[:3] == ["gh", "pr", "list"]:
            # The snapshot's batch and the digest's own read differ by exactly the fields asked for.
            return json.dumps(self.heads if "headRefName" in cmd[-1] else self.prs)
        if cmd[:3] == ["gh", "pr", "view"]:
            return json.dumps({"statusCheckRollup": self.rollup_reread[int(cmd[3])]})
        if cmd[:2] == ["gh", "api"]:
            return self.api(cmd[2])
        raise AssertionError(f"unexpected command {cmd}")

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
            rows = self.reviews if number == 7200 else self.pr_comments.get(number, [])
            if number != 7200 and (w := re.search(r"since=([\w:.Z-]+)", path)):
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


def test_a_cell_whose_review_label_is_none_reports_no_queue_instead_of_erroring():
    # `none` is a real value on main's roster (coordinator, heavy-a, heavy-b, operator). "I have no
    # review queue" is a fact about the roster; a section that cannot tell them apart makes every
    # heavy-tier tick print a false failure.
    out = text(sandbox="agent-uplevel-heavy-b", beats=[heartbeat("agent-uplevel-heavy-b", 3)])
    assert has(out, "== no review queue (0)") and not has(out, "ERROR identities")


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


def test_the_coordinators_age_prints_and_a_fresh_one_raises_no_rule():
    assert has(text(), "coordinator age 5.0m") and not has(text(), "UR-162")


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


# --- the review queue -----------------------------------------------------------------------


def test_a_queue_pr_prints_head_merge_state_gate_and_plan_text():
    out = text()
    line = row(out, 7200)
    assert THEIRS_HEAD[:9] in line and "BEHIND" in line and "SUCCESS" in line
    assert "Plan text: not stated" in line


def test_the_plan_text_line_is_read_through_the_markdown_that_wraps_it():
    # Measured on the live open PRs: the line is written `- **Plan text:** none.`, so a
    # startswith("Plan text:") scan finds it on none of them and every PR prints the default.
    out = text(
        prs=[pr(7200, labels=["review:ops-b"], head=THEIRS_HEAD, draft=False)],
        heads=[head_row(7200, THEIRS, PLAN)],
    )
    assert "Plan text: none" in row(out, 7200)


def test_an_unreviewed_pr_does_not_claim_ur92s_default():
    # UR-92's `Plan text: none` lives in the REVIEW body and is conditional on the diff's paths. A
    # PR nobody reviewed has no such line, and printing the default would post my name under a claim
    # I never made -- the same class as an untested mechanism asserted in prose.
    out = text(
        reviews=[],
        prs=[pr(7200, labels=["review:ops-b"], head=THEIRS_HEAD, draft=False)],
        heads=[head_row(7200, THEIRS, "# x\n\n## Body\nno such line\n")],
    )
    assert "not stated" in row(out, 7200) and "Plan text: none" not in out


def test_an_in_flight_gate_names_the_jobs_still_running():
    out = text(
        prs=[pr(7200, labels=["review:ops-b"], head=THEIRS_HEAD, draft=False, rollup=[gate(None, "IN_PROGRESS")])],
        heads=[head_row(7200, THEIRS, PLAN)],
        jobs=[
            {"name": "Feature check (fake AI)", "status": "in_progress"},
            {"name": "CI Gate (Required Checks)", "status": "in_progress"},
        ],
    )  # fmt: skip
    line = row(out, 7200)
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
    fake, out = run_tick(
        prs=[pr(7200, labels=["review:ops-b"], head=THEIRS_HEAD, draft=False, rollup=capped)],
        heads=[head_row(7200, THEIRS, PLAN)],
        rollup_reread={7200: [gate("SUCCESS")]},
    )
    assert fake.asked("gh pr view 7200")
    assert "gate=SUCCESS" in row(out, 7200)


# --- my own open PRs ------------------------------------------------------------------------


def test_my_open_prs_are_derived_from_my_branches():
    # Labels carry cell:a on ops-a's PRs and no cell at all on some of mine, and the author login is
    # the owner's for every PR (UR-168): the branch set is the only ownership fact that always holds.
    out = text()
    assert has(out, "== mine (2)") and has(out, "#7164") and has(out, "#7158")


def test_a_pr_on_a_branch_i_do_not_hold_is_not_mine():
    out = text(
        heads=[
            head_row(7158, THEIRS, PLAN),
            head_row(7164, THEIRS, PLAN),
            head_row(7200, THEIRS, PLAN),
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
        heads=[head_row(7164, MY_BRANCH, PLAN, "an [r151] follow-up")],
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
        heads=[head_row(7151, MY_BRANCH, PLAN, "[UR-48] fix: re-anchor a panel leg")],
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
        heads=[head_row(7164, MY_BRANCH, PLAN, "an unrelated title")],
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
    assert tick.held_claims(PKG, ["r157", "r151", "r181", "r172"], mine) == ["r181"]
    # by the field alone (the title names nothing here, `**PR:**` on [r172] names my #7164)
    field = PKG.replace("none yet. (ruling 172", "#7164. (ruling 172")
    assert tick.held_claims(field, ["r181", "r172"], [{"number": 7164, "title": "nothing here"}]) == [
        "r172"
    ]  # fmt: skip
    # neither: a [UR-nn] fix on a queue package's branch titles no package and no field names it
    assert tick.held_claims(PKG, ["r157", "r181", "r172"], []) == []
    assert tick.held_claims(PKG, ["r181"], [{"number": 7151, "title": "[UR-48] fix: a leg"}]) == []
    # a queue token with no block here (an F2.3 batch, a trigger) is not a package and holds nothing
    assert tick.held_claims(PKG, ["F2.3", "O3.4"], mine) == []


def test_a_hold_and_a_claimable_are_never_both_printed():
    # The branch order in `build` is the rule: the hold wins and the offer is suppressed, so a lane
    # never reads a package it may claim from a digest that also says it is mid-flight.
    mine = [{"number": 7164, "title": "[r181] the lane-tick digest"}]
    assert tick.held_claims(PKG, ["r181", "r172"], mine) == ["r181"]
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
    assert has(out, "ERROR disk") and has(out, "#7158") and has(out, "#7200")


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
    # to prevent. So a 30-PR queue must print every row AND name the excess.
    # Measured growth: one line per PR row on an 11-line default, so 80 rows puts the digest past
    # the cap. The number is checked against the printed output, not against the expression that
    # produced it -- and it excludes the NOTE itself, which is the shape worth pinning.
    n = tick.CAP_LINES
    many = [
        pr(7300 + i, labels=["review:ops-b"], head=THEIRS_HEAD, draft=False, title=f"leg {i}")
        for i in range(n)
    ]
    heads = [head_row(7300 + i, THEIRS, PLAN, f"leg {i}") for i in range(n)]
    lines = text(prs=many, heads=heads).splitlines()
    note = [ln for ln in lines if "lines over" in ln]
    assert len(note) == 1
    excess = int(note[0].split()[1])
    assert excess > 0 and excess == len(lines) - 1 - n
    assert len(has("\n".join(lines), "leg 79")) == 1  # the LAST row survives: it reports, not cuts
    assert f"== review:ops-b ({n})" in "\n".join(lines)


def test_the_digest_stays_under_the_programmes_character_bound():
    # status_draft keeps a coordinator's whole status under this; a lane's reading is a subset.
    assert len(text()) <= status.LIMIT
