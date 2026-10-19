#!/usr/bin/env python3
"""Tests for scripts/uplevel/coordinator_snapshot.py (ruling 152), with no network.

Run explicitly; outside testpaths (like every scripts/test_*.py gate suite):

    uv run python -m pytest scripts/test_coordinator_snapshot.py -q

Every gh and git call the script makes goes through one runner; these tests pass a fake that
answers by command shape and records what was asked, and a fixed clock. Each test changes one
answer of a shared green scenario, so a passing arm and a failing arm differ by one fact.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "uplevel" / "coordinator_snapshot.py"


def _load():
    spec = importlib.util.spec_from_file_location("coordinator_snapshot", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["coordinator_snapshot"] = mod
    spec.loader.exec_module(mod)
    return mod


snap = _load()

NOW = datetime(2026, 10, 13, 15, 0, 0, tzinfo=UTC)
REPO = "o/r"
HEAD = "a1b2c3d" + "e" * 33  # a full sha whose 7-char prefix the reviews below name
BASE = "b" * 40  # the PR's merge-base with origin/main
RUN_BASE = "d" * 40  # the main the gate's run merged the head into
TIP = "f" * 40
GATE_RUN = 900
CHECKOUT_JOB = 77


def t(delta: timedelta) -> str:
    return snap.iso(NOW + delta)


def comment(cid, number, body, created, updated=None, user="mikesvoboda", pr=False):
    kind = "pull" if pr else "issues"
    return {
        "id": cid,
        "issue_url": f"https://api.github.com/repos/{REPO}/issues/{number}",
        "html_url": f"https://github.com/{REPO}/{kind}/{number}#issuecomment-{cid}",
        "user": {"login": user},
        "created_at": created,
        "updated_at": updated or created,
        "body": body,
    }


def coordinator_heartbeat(extra="read-through: 2026-10-13T14:30:00Z"):
    body = "<!-- heartbeat:agent-uplevel-coordinator -->\ncoordinator · 14:55Z · tick\n" + extra
    return comment(1, 6958, body, t(-timedelta(days=2)), t(-timedelta(minutes=5)))


def gate(conclusion="SUCCESS", status="COMPLETED"):
    return {
        "__typename": "CheckRun",
        "name": "CI Gate (Required Checks)",
        "status": status,
        "conclusion": conclusion,
        "startedAt": t(-timedelta(hours=1)),
        "detailsUrl": f"https://github.com/{REPO}/actions/runs/{GATE_RUN}/job/5",
    }


def filler_check(name="Backend Unit Tests"):
    """A non-gate check run, to build a rollup long enough to hit the list-API cap."""
    return {
        "__typename": "CheckRun",
        "name": name,
        "status": "COMPLETED",
        "conclusion": "SUCCESS",
        "startedAt": t(-timedelta(hours=1)),
        "detailsUrl": f"https://github.com/{REPO}/actions/runs/901/job/1",
    }


def checkout_log(head=HEAD, base=RUN_BASE):
    return (
        "2026-10-13T15:13:40Z ##[group]Checking out the ref\n"
        f"2026-10-13T15:13:41Z HEAD is now at 0a1b2c3 Merge {head} into {base}\n"
    )


def run(conclusion, status="completed", head=TIP, minutes=10):
    return {
        "databaseId": minutes,
        "status": status,
        "conclusion": conclusion,
        "headSha": head,
        "createdAt": t(-timedelta(minutes=minutes)),
        "event": "push",
        "url": "u",
    }


class FakeRunner:
    """Answers each command by the first rule whose needle the joined command contains."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.rules: dict[str, object] = {}
        self.heartbeats = [
            coordinator_heartbeat(),
            comment(
                2,
                6958,
                "<!-- heartbeat:agent-uplevel-backend -->\nbackend · working",
                t(-timedelta(days=2)),
                t(-timedelta(minutes=30)),
            ),
            comment(
                3,
                6958,
                "<!-- heartbeat:agent-uplevel-heavy -->\nheavy · paused · queue empty (ruling 88)",
                t(-timedelta(days=2)),
                t(-timedelta(minutes=300)),
            ),
            comment(
                4,
                6958,
                "<!-- heartbeat:agent-uplevel-docs -->\ndocs · working",
                t(-timedelta(days=2)),
                t(-timedelta(minutes=19)),
            ),
            comment(5, 6958, "a plain note, not a heartbeat", t(-timedelta(days=1))),
        ]
        self.repo_comments = [
            comment(10, 7001, "Review: approve\nHead reviewed: `a1b2c3d`", t(-timedelta(minutes=20)), pr=True),
            comment(11, 6854, "<!-- status:uplevel-coordinator -->\nstatus", t(-timedelta(days=1)), t(-timedelta(minutes=9))),
            comment(12, 6958, "<!-- heartbeat:agent-uplevel-backend -->\nx", t(-timedelta(days=1)), t(-timedelta(minutes=8))),
            comment(13, 6854, "URGENT PATH · red `main`", t(-timedelta(minutes=7))),
            comment(14, 6854, "BINDING NOW · ruling 152", t(-timedelta(minutes=6))),
            comment(15, 6854, "BINDING NOW · old record", t(-timedelta(hours=49)), t(-timedelta(minutes=5))),
            comment(16, 7001, "## coverage", t(-timedelta(minutes=4)), user="github-actions[bot]", pr=True),
        ]  # fmt: skip
        self.owner_comments = [
            comment(20, 6854, "BINDING NOW · live one", t(-timedelta(hours=47))),
            comment(21, 6854, "BINDING NOW · lapsed one", t(-timedelta(hours=49)), t(-timedelta(hours=1))),
            comment(22, 6854, "Owner record, not binding now", t(-timedelta(hours=2))),
        ]  # fmt: skip
        self.prs = [
            {
                "number": 7001,
                "title": "ready PR",
                "isDraft": False,
                "labels": [{"name": "lane:docs"}],
                "headRefOid": HEAD,
                "mergeStateStatus": "CLEAN",
                "statusCheckRollup": [gate()],
            },
            {
                "number": 7002,
                "title": "draft PR",
                "isDraft": True,
                "labels": [],
                "headRefOid": "c" * 40,
                "mergeStateStatus": "CLEAN",
                "statusCheckRollup": [gate()],
            },
        ]
        self.reviews = [
            {"id": 30, "created_at": t(-timedelta(hours=2)), "user": "ops-b", "body": "Review: approve\nHead: `a1b2c3d`"}
        ]  # fmt: skip
        self.ci_runs = [run("", status="in_progress", minutes=1), run("success", minutes=30)]
        # The run base is 3 merges behind the tip; the older merge-base is 10 behind.
        self.merges_behind = {RUN_BASE: "3", BASE: "10"}
        self.main_files = {RUN_BASE: "docs/a.md\n", BASE: "docs/a.md\ndocs/b.md\n"}
        self.pr_files = "docs/b.md\n"
        # Per-PR rollups that differ from the batched list's (the list caps each PR at 100 entries).
        self.pr_rollups: dict[int, list] = {}
        self.checkout_jobs = [{"id": 99, "steps": 40}, {"id": CHECKOUT_JOB, "steps": 5}]
        self.log = checkout_log()
        # ruling 164: the UR-106 own-diff reads, the merged list, per-PR comments and doc fields.
        self.own_diffs: dict[str, str] = {}  # keyed by the "<base>..<rev>" range argument
        self.merge_bases: dict[str, str] = {}  # "<root>::<rev>" -> base; see merge-base below
        self.parents: dict[
            str, tuple[str, str]
        ] = {}  # merge commit -> (main at merge, landed head)
        self.merged_prs: list[dict] = []  # REST /pulls rows: number/merged_at/merge_commit_sha/body
        self.pr_issue_comments: dict[int, list] = {}  # merged-PR Review: reads (7001 uses .reviews)
        # ruling 181's commit leg: PR number -> [(stamp, sha, subject)], filtered by --since below.
        self.pr_commits: dict[int, list[tuple[str, str, str]]] = {}
        # `gh pr view --json files` answers; keyed by PR number.
        self.pr_files_by_number: dict[int, list[str]] = {7001: ["docs/b.md"], 7002: ["docs/c.md"]}
        self.pr_bodies: dict[int, str] = {}

    def fail(self, needle: str, message: str = "HTTP 504") -> None:
        self.rules[needle] = snap.CommandError(message)

    def __call__(self, cmd):
        cmd = list(cmd)
        self.calls.append(cmd)
        joined = " ".join(cmd)
        for needle, answer in self.rules.items():
            if needle in joined:
                if isinstance(answer, Exception):
                    raise answer
                return answer
        return self.default(cmd, joined)

    def default(self, cmd, joined):
        if cmd[:2] == ["gh", "api"]:
            path = cmd[2]
            if "/issues/6958/comments" in path:
                return json.dumps(self.heartbeats[:2]) + json.dumps(self.heartbeats[2:])
            if "/issues/6854/comments" in path:
                return json.dumps(self.owner_comments)
            if "/issues/comments?" in path:
                # The real endpoint returns only comments touched at or after `since`, so the fake
                # must too: §6's activity read is conditional on the window BECAUSE §2's is not the
                # whole record, and a fake that answers every window with every comment turns a
                # "no activity" pin green on a comment the API would never have handed over.
                since = re.search(r"since=([^&]+)", path)
                return json.dumps(
                    [
                        c
                        for c in self.repo_comments
                        if not since or c["updated_at"] >= since.group(1)
                    ]
                )  # fmt: skip
            if "/pulls?" in path:  # §7 merged-since-cursor list (rows carry body, as REST does)
                return json.dumps(self.merged_prs)
            m = re.search(r"/issues/([0-9]+)/comments", path)
            if m:
                number = int(m.group(1))
                if number == 7001:  # §3's review read keeps its own fixture
                    return json.dumps(self.reviews)
                return json.dumps(self.pr_issue_comments.get(number, []))
            if path.startswith(f"repos/{REPO}/actions/runs/{GATE_RUN}/jobs"):
                return json.dumps(self.checkout_jobs)
            if path == f"repos/{REPO}/actions/jobs/{CHECKOUT_JOB}/logs":
                return self.log
        if cmd[:3] == ["gh", "run", "list"]:
            if "ci.yml" in joined:
                return json.dumps(self.ci_runs)
            return json.dumps([run("success")])
        if cmd[:3] == ["gh", "pr", "list"]:
            return json.dumps(self.prs)
        if cmd[:3] == ["gh", "pr", "view"]:
            number = int(cmd[3])
            if "files" in cmd[cmd.index("--json") :]:  # UR-106's <the PR's files>
                return json.dumps({"files": [{"path": p} for p in self.pr_files_by_number.get(number, [])]})  # fmt: skip
            rollup = self.pr_rollups.get(number)
            if rollup is None:  # the fake's batched answer, as if the cap never bit
                rollup = next(p["statusCheckRollup"] for p in self.prs if p["number"] == number)
            return json.dumps({"statusCheckRollup": rollup})
        if cmd[:2] == ["git", "fetch"]:
            return ""
        if cmd[:2] == ["git", "rev-parse"]:
            arg = cmd[-1]
            if arg.endswith("^1"):  # main as it stood at the merge = the merged PR's base root
                return self.parents[arg[:-2]][0] + "\n"
            if arg.endswith("^2"):  # the landed head = the merge commit's second parent
                return self.parents[arg[:-2]][1] + "\n"
            return TIP + "\n"
        if cmd[:2] == ["git", "merge-base"]:
            root, rev = cmd[-2], cmd[-1]
            if f"{root}::{rev}" in self.merge_bases:  # a base the test declared wins
                return self.merge_bases[f"{root}::{rev}"] + "\n"
            # git resolves an unambiguous abbreviation against what the repo holds, and the
            # implementation passes the review's named prefix straight through -- so a declared
            # full sha answers its own prefix, and only its own.
            cands = [
                k
                for k in self.merge_bases
                if k.startswith(f"{root}::") and k.split("::", 1)[1].startswith(rev)
            ]
            if len(cands) == 1:
                return self.merge_bases[cands[0]] + "\n"
            if root == "origin/main":  # the live base of an OPEN head
                return BASE + "\n"
            # An undeclared root means the implementation picked a base root nobody asserted.
            # Defaulting it would hide the vacuity bug: for a merged PR, merge-base origin/main
            # <head> *is* the head, so the own diff is empty and every carry check passes for free.
            raise AssertionError(f"undeclared merge-base root {root} for {rev[:9]}")
        if cmd[:2] == ["git", "rev-list"]:
            return self.merges_behind[cmd[-1].split("..")[0]] + "\n"
        if cmd[:2] == ["git", "log"]:  # ruling 181: commits on a PR head since that agent's beat
            number = int(cmd[-1].rsplit("/", 1)[-1])
            since = next(a.split("=", 1)[1] for a in cmd if a.startswith("--since="))
            epoch = int(snap.parse_time(since).timestamp())
            # git's --since filters by commit date, so the fake must filter too: a pin about
            # "commits SINCE THE BEAT" that reads an unfiltered fixture measures the fixture.
            # Rows print as `<commit-epoch>\\t<sha>\\t<subject>`, which is the %ct%x09%H%x09%s the
            # implementation asks for — a fixture that printed ISO here would pass a wrong format.
            return "".join(
                f"{int(snap.parse_time(st).timestamp())}\t{sha}\t{subj}\n"
                for st, sha, subj in sorted(self.pr_commits.get(number, []))
                if int(snap.parse_time(st).timestamp()) >= epoch
            )
        if cmd[:2] == ["git", "diff"]:
            if cmd[-1] == "origin/main":
                return self.main_files[cmd[-2]]
            if "--" in cmd:  # the UR-106 own diff: keyed by its exact <base>..<rev> range
                key = cmd[2]
                if key in self.own_diffs:
                    return self.own_diffs[key]
                # git resolves the review's 7-char prefix against the repo, so the implementation
                # hands it to ``diff`` verbatim; a declared full-sha range answers its own prefix.
                base, _, rev = key.partition("..")
                cands = [
                    k
                    for k in self.own_diffs
                    if k.split("..", 1)[0] == base and k.split("..", 1)[1].startswith(rev)
                ]
                if len(cands) == 1:
                    return self.own_diffs[cands[0]]
                raise AssertionError(f"undeclared own diff {key}")
            # From the run base (not an ancestor of the head) the diff would carry main's file too.
            return self.pr_files if cmd[-2] == BASE else "docs/a.md\n" + self.pr_files
        raise AssertionError(f"unexpected command {cmd}")


def build(fake: FakeRunner, since: datetime | None = None) -> dict:
    return snap.Snapshot(REPO, fake, lambda: NOW, since).build()


def pr(data: dict, number: int = 7001) -> dict:
    return next(p for p in data["prs"]["items"] if p["number"] == number)


def rendered_pr_block(data: dict, number: int = 7001) -> list[str]:
    """Section 3's lines for one PR: its headline plus the six-space-indented detail rows.

    Needed because ``"STALE" in render_text(...)`` is a false-positive instrument — section 6
    prints the same word for an old heartbeat, so a whole-report search can never say that a
    *verdict* was misread.
    """
    lines = snap.render_text(data).splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(f"  #{number} "))
    block = [lines[start]]
    for line in lines[start + 1 :]:
        if not line.startswith("      "):
            break
        block.append(line)
    return block


# --- 1. cursor ---------------------------------------------------------------------------


def test_cursor_read_from_the_coordinator_heartbeat():
    fake = FakeRunner()
    data = build(fake)
    assert data["cursor"]["cursor"] == "2026-10-13T14:30:00Z"
    assert data["cursor"]["heartbeat_id"] == 1
    assert data["cursor"]["now"] == "2026-10-13T15:00:00Z"
    asked = [c[2] for c in fake.calls if c[:2] == ["gh", "api"] and "/issues/comments?" in c[2]]
    assert asked == [f"repos/{REPO}/issues/comments?since=2026-10-13T14:30:00Z&per_page=100"]


def test_cursor_absent_falls_back_to_now_minus_two_hours():
    fake = FakeRunner()
    fake.heartbeats[0] = coordinator_heartbeat(extra="no cursor line here")
    data = build(fake)
    assert data["cursor"]["cursor"] == "2026-10-13T13:00:00Z"
    assert data["cursor"]["source"].startswith("default")


def test_since_overrides_the_heartbeat_cursor():
    data = build(FakeRunner(), since=datetime(2026, 10, 13, 9, 0, tzinfo=UTC))
    assert data["cursor"]["cursor"] == "2026-10-13T09:00:00Z"
    assert data["cursor"]["source"] == "--since"


def test_since_flag_parses_and_bad_args_exit_two(capsys):
    fake = FakeRunner()
    assert snap.main(["--since", "2026-10-13T09:00:00Z", "--json"], fake, lambda: NOW) == 0
    assert json.loads(capsys.readouterr().out)["cursor"]["cursor"] == "2026-10-13T09:00:00Z"
    with pytest.raises(SystemExit) as exc:
        snap.main(["--since", "yesterday"], fake, lambda: NOW)
    assert exc.value.code == 2


# --- 2. comments -------------------------------------------------------------------------


def test_binding_now_is_live_under_48_hours_and_lapsed_after():
    items = {c["id"]: c for c in build(FakeRunner())["comments"]["items"]}
    assert items[14]["flag"] == "BINDING NOW live"
    assert items[15]["flag"] == "BINDING NOW lapsed"


def test_urgent_path_is_flagged():
    items = {c["id"]: c for c in build(FakeRunner())["comments"]["items"]}
    assert items[13]["flag"] == "URGENT PATH"
    assert items[10]["flag"] is None


def test_marker_comments_are_counted_not_listed():
    com = build(FakeRunner())["comments"]
    ids = {c["id"] for c in com["items"]}
    assert com["marker_count"] == 2
    assert not ids & {11, 12}
    assert com["bot"] == {"7001": 1}
    assert 16 not in ids


def test_live_binding_now_on_6854_lists_only_the_last_48_hours():
    fake = FakeRunner()
    data = build(fake)
    assert [b["id"] for b in data["binding_now"]["items"]] == [20]
    asked = [c[2] for c in fake.calls if c[:2] == ["gh", "api"] and "/6854/" in c[2]]
    assert asked == [f"repos/{REPO}/issues/6854/comments?since=2026-10-11T15:00:00Z&per_page=100"]


# --- 3. PRs and approvals ------------------------------------------------------------------


def test_approval_sha_matching_the_head():
    p = pr(build(FakeRunner()))
    assert p["approval"]["sha"] == "a1b2c3d"
    assert p["approval"]["matches_head"] is True
    assert p["gate"] == "SUCCESS"
    assert p["merge_base"] == BASE


def test_approval_sha_on_an_older_head_is_stale():
    fake = FakeRunner()
    fake.reviews.append(
        {
            "id": 31,
            "created_at": t(-timedelta(hours=1)),
            "user": "ops-b",
            "body": "Review: approve\nHead: 0123456789abcdef (prior approve was `a1b2c3d`)",
        }
    )
    p = pr(build(fake))
    assert p["approval"] == {
        "id": 31,
        "by": "ops-b",
        "sha": "0123456789abcdef",
        "matches_head": False,
    }
    assert "STALE" in snap.render_text(build(fake))


def test_bold_verdict_first_line_counts_as_approval():
    # Verdict first lines in the wild (2026-10-13 census over 9 PRs): `Review: approve`,
    # `Review: **approved**` (6151128403), `Review: approve at head <sha>`. The literal
    # startswith("Review: approve") missed the bold one, so a live key read back as STALE
    # and invited a void (defect note 6153121259 §1; frontend's 6152497298 says the same).
    fake = FakeRunner()
    fake.reviews.append(
        {
            "id": 32,
            "created_at": t(-timedelta(minutes=5)),
            "user": "mikesvoboda",
            "body": "Review: **approved**\nHead: `a1b2c3d`\n",
        }
    )
    p = pr(build(fake))
    assert p["approval"]["id"] == 32
    assert p["approval"]["matches_head"] is True
    block = rendered_pr_block(build(fake), 7001)
    assert "approve=a1b2c3d(=head, 32)" in block[0]
    assert "STALE" not in block[0]
    assert not [ln for ln in block[1:] if "latest review:" in ln]


def test_changes_requested_and_negated_verdicts_are_not_approvals():
    fake = FakeRunner()
    fake.reviews.append(
        {
            "id": 33,
            "created_at": t(-timedelta(minutes=5)),
            "user": "x",
            "body": "Review: changes requested",
        }
    )
    fake.reviews.append(
        {
            "id": 34,
            "created_at": t(-timedelta(minutes=4)),
            "user": "x",
            "body": "Review: **not approved**",
        }
    )
    p = pr(build(fake))
    # The earlier real approval still stands; neither new line counts as an approval.
    assert p["approval"]["id"] == 30
    assert p["latest_review"].startswith("Review: **not approved**")


def test_drafts_get_no_review_read_and_no_legs():
    fake = FakeRunner()
    p = pr(build(fake), 7002)
    assert "approval" not in p
    assert "legs" not in p
    assert not any("/issues/7002/comments" in " ".join(c) for c in fake.calls)


def test_gate_states():
    assert snap.gate_state([]) == "absent"
    assert snap.gate_state([gate(conclusion="", status="IN_PROGRESS")]) == "IN_PROGRESS"
    assert snap.gate_state([gate(conclusion="FAILURE")]) == "FAILURE"


def test_a_gate_past_the_list_api_rollup_cap_is_still_read():
    # Measured 2026-10-13 on #7070: `gh pr list --json statusCheckRollup` returns at most 100
    # entries per PR — it has 129, and both `CI Gate` rows fall past the cut — so §3 printed
    # gate=absent for a PR whose gate was green (defect note 6153121259 §3, cause undiagnosed
    # by the coordinator). `gh pr view --json statusCheckRollup` returns all 129. `absent` is
    # the one reading the capped batch cannot be trusted for, so that is what gets re-read.
    fake = FakeRunner()
    full = [filler_check(f"check {i}") for i in range(100)] + [gate()]
    fake.prs[0]["statusCheckRollup"] = full[:100]  # what the batch hands back: a truncated prefix
    fake.pr_rollups[7001] = full  # what the per-PR read hands back
    assert snap.gate_state(fake.prs[0]["statusCheckRollup"]) == "absent"  # the batch's own reading
    p = pr(build(fake))
    assert p["gate"] == "SUCCESS"
    assert p["gate_run"] == GATE_RUN
    asked = [c for c in fake.calls if c[:3] == ["gh", "pr", "view"]]
    assert [c[3] for c in asked] == ["7001"], "the cap fix must re-read only the suspect PR"


def test_a_short_rollup_without_a_gate_is_not_reread():
    # The other side of the control: a PR whose batch is short genuinely has no gate, and the
    # fix must not spend a per-PR call on every such PR each tick.
    fake = FakeRunner()
    fake.prs[1]["statusCheckRollup"] = [filler_check()]
    p = pr(build(fake), 7002)
    assert p["gate"] == "absent"
    assert not [c for c in fake.calls if c[:3] == ["gh", "pr", "view"]]


# --- 4. UR-102 legs ----------------------------------------------------------------------


def test_legs_measure_from_the_run_base_not_the_merge_base():
    """The run base is 3 merges behind (pass) while the merge-base is 10 behind; the main file
    the merge-base diff would share with the PR landed before the run, so it is no overlap."""
    fake = FakeRunner()
    p = pr(build(fake))
    assert p["gate_run"] == GATE_RUN
    assert p["leg_base"] == {
        "run_id": GATE_RUN,
        "merge_base": BASE,
        "run_base": RUN_BASE,
        "used": "run",
    }
    assert p["legs"]["behind"] == {"merges": 3, "pass": True}
    assert p["legs"]["overlap"] == {"paths": [], "pass": True}
    assert p["legs"]["main_ci"] == {"conclusion": "success", "pass": True}
    assert p["merge_without_update"] is True
    assert [
        "git",
        "rev-list",
        "--count",
        "--first-parent",
        f"{RUN_BASE}..origin/main",
    ] in fake.calls
    assert ["git", "diff", "--name-only", RUN_BASE, "origin/main"] in fake.calls
    assert ["git", "diff", "--name-only", BASE, HEAD] in fake.calls  # the PR's own files
    logs = [c for c in fake.calls if c[:2] == ["gh", "api"] and c[2].endswith("/logs")]
    assert logs == [["gh", "api", f"repos/{REPO}/actions/jobs/{CHECKOUT_JOB}/logs"]]
    text = snap.render_text(build(FakeRunner()))
    assert f"base: run {RUN_BASE[:9]} (run {GATE_RUN}) · merge-base {BASE[:9]}" in text


def test_four_merges_behind_the_run_base_fails_the_first_leg():
    fake = FakeRunner()
    fake.merges_behind[RUN_BASE] = "4"
    p = pr(build(fake))
    assert p["legs"]["behind"] == {"merges": 4, "pass": False}
    assert p["merge_without_update"] is False


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ("no_run_id", "no run id"),
        ("no_checkout_job", "no successful checkout job"),
        ("no_merge_line", "names no checkout merge"),
        ("other_head", "not the head"),
        ("log_fails", "HTTP 404"),
    ],
)
def test_an_unreadable_run_base_falls_back_to_the_merge_base(change, reason):
    fake = FakeRunner()
    if change == "no_run_id":
        fake.prs[0]["statusCheckRollup"][0].pop("detailsUrl")
    elif change == "no_checkout_job":
        fake.checkout_jobs = []
    elif change == "no_merge_line":
        fake.log = "no checkout here\n"
    elif change == "other_head":
        fake.log = checkout_log(head="9" * 40)
    else:
        fake.fail("/logs", "HTTP 404")
    data = build(fake)
    p = pr(data)
    assert p["leg_base"]["used"] == "merge-base fallback"
    assert reason in p["leg_base"]["error"]
    assert p["legs"]["behind"] == {"merges": 10, "pass": False}
    assert p["legs"]["overlap"] == {"paths": ["docs/b.md"], "pass": False}
    assert "(base: merge-base fallback" in snap.render_text(data)


def test_a_shared_path_fails_the_overlap_leg():
    fake = FakeRunner()
    fake.pr_files = "docs/a.md\ndocs/b.md\n"
    p = pr(build(fake))
    assert p["legs"]["overlap"] == {"paths": ["docs/a.md"], "pass": False}
    assert p["merge_without_update"] is False


def test_red_main_fails_the_third_leg():
    fake = FakeRunner()
    fake.ci_runs = [run("failure", minutes=5), run("success", minutes=30)]
    p = pr(build(fake))
    assert p["legs"]["main_ci"] == {"conclusion": "failure", "pass": False}
    assert p["merge_without_update"] is False


def test_no_legs_without_a_green_gate():
    fake = FakeRunner()
    fake.prs[0]["statusCheckRollup"] = [gate(conclusion="FAILURE")]
    assert "legs" not in pr(build(fake))


# --- 5. main -----------------------------------------------------------------------------


def test_cancelled_main_run_is_not_red():
    fake = FakeRunner()
    fake.ci_runs = [run("cancelled", minutes=5), run("success", minutes=30)]
    data = build(fake)
    assert data["main"]["ci_latest"]["conclusion"] == "cancelled"
    assert data["main"]["ci_last_completed"]["conclusion"] == "success"
    assert pr(data)["legs"]["main_ci"]["pass"] is True


def test_main_section_reads_each_workflow():
    fake = FakeRunner()
    data = build(fake)
    assert data["main"]["tip"] == TIP
    assert data["main"]["ci_at_tip"]["conclusion"] is None
    assert data["main"]["nightly_full_gate"]["conclusion"] == "success"
    nightly = next(c for c in fake.calls if "nightly-full-gate.yml" in c)
    assert nightly[nightly.index("--event") + 1] == "schedule"
    assert any("flaky-test-detection.yml" in c for c in fake.calls)
    assert any("deploy.yml" in c for c in fake.calls)


# --- 6. heartbeats -----------------------------------------------------------------------


def test_heartbeat_age_over_twenty_minutes_is_flagged():
    items = {h["agent"]: h for h in build(FakeRunner())["heartbeats"]["items"]}
    assert set(items) == {
        "agent-uplevel-coordinator",
        "agent-uplevel-backend",
        "agent-uplevel-heavy",
        "agent-uplevel-docs",
    }
    assert items["agent-uplevel-backend"]["stale"] is True
    assert items["agent-uplevel-docs"]["stale"] is False
    assert items["agent-uplevel-coordinator"]["age_min"] == 5.0
    assert items["agent-uplevel-heavy"]["paused"] is True
    assert items["agent-uplevel-backend"]["paused"] is False


def _coordinator_beat(fake: FakeRunner, minutes: float) -> None:
    """Replace the fixture's fresh coordinator beat with one MINUTES old."""
    fake.heartbeats[0] = comment(
        1,
        6958,
        "<!-- heartbeat:agent-uplevel-coordinator -->\ncoordinator · tick\nread-through: x",
        t(-timedelta(days=2)),
        t(-timedelta(minutes=minutes)),
    )


def test_a_coordinator_beat_between_twenty_and_ninety_minutes_old_is_not_stale():
    # [r239], ruling 239 item 4: the coordinator's 30-minute loop can leave its heartbeat about
    # 90 minutes old (a tick up to 60 plus up to 30 until the next fire), so the UR-162 trigger
    # is the coordinator's identity at 90, not the every-agent 20 the code shipped. The default
    # fixture's 30-minute backend beat keeps the lane rows' 20 below.
    fake = FakeRunner()
    _coordinator_beat(fake, 34)
    items = {h["agent"]: h for h in build(fake)["heartbeats"]["items"]}
    assert items["agent-uplevel-coordinator"]["stale"] is False
    assert items["agent-uplevel-backend"]["stale"] is True  # 30m: a lane keeps its own 20


def test_a_coordinator_beat_past_ninety_minutes_is_stale():
    fake = FakeRunner()
    _coordinator_beat(fake, 91)
    items = {h["agent"]: h for h in build(fake)["heartbeats"]["items"]}
    assert items["agent-uplevel-coordinator"]["stale"] is True


def test_the_stale_print_names_the_row_own_threshold():
    # §6 renders the number, not a bare flag: a 91-minute coordinator row says >90m and a
    # 30-minute backend row says >20m, so a reader of the report sees which rule tripped
    # without knowing the code. One shared constant can say only one of the two.
    fake = FakeRunner()
    _coordinator_beat(fake, 91)
    lines = [
        ln
        for ln in snap.render_text(build(fake)).splitlines()
        if "agent-uplevel-coordinator" in ln or "agent-uplevel-backend" in ln
    ]
    coord = next(ln for ln in lines if "agent-uplevel-coordinator" in ln)
    lane = next(ln for ln in lines if "agent-uplevel-backend" in ln)
    assert ">90m" in coord and "STALE" in coord, coord
    assert ">20m" in lane and "STALE" in lane, lane


def test_status_draft_note_names_each_row_own_threshold():
    # [r239] box 2: the status comment's stale note "(> N min, UR-162)" carries the row's own
    # threshold -- 90 for the coordinator, 20 for a lane -- instead of one constant for all.
    # UR-166's 20-minute LISTING is unchanged, so a 34-minute coordinator beat still lists (the
    # 20-minute rule), but its row names >90: the reader sees it is not yet a UR-162 raise.
    sd = _load_status_draft()
    fake = FakeRunner()
    _coordinator_beat(fake, 91)
    body = sd.render(build(fake), questions=[])
    section = body.split("== Stalled and stale heartbeats", 1)[1].split("\n== ", 1)[0]
    coord = next(ln for ln in section.splitlines() if "agent-uplevel-coordinator" in ln)
    lane = next(ln for ln in section.splitlines() if "agent-uplevel-backend" in ln)
    assert "(> 90 min, UR-162)" in coord, coord
    assert "(> 20 min, UR-162)" in lane, lane
    # the unchanged listing: a 34-minute coordinator beat lists with its own number, though
    # the raise band has not opened.
    fake2 = FakeRunner()
    _coordinator_beat(fake2, 34)
    body2 = sd.render(build(fake2), questions=[])
    section2 = body2.split("== Stalled and stale heartbeats", 1)[1].split("\n== ", 1)[0]
    coord2 = next(ln for ln in section2.splitlines() if "agent-uplevel-coordinator" in ln)
    assert "(> 90 min, UR-162)" in coord2, coord2


def test_a_stalled_agent_is_flagged_beside_the_stale_flag():
    # [r239] box 4, ruling 245: an agent is stalled past THREE of its own UR-36 intervals --
    # 90 for a lane on the 30-minute fallback ([r193] merged), 45 for heavy on 15, 90 for the
    # coordinator and the operator -- printed beside UR-162's threshold, which is a different
    # rule about the same beat. A 50-minute docs beat is stale (20) but NOT stalled (90); a
    # 50-minute heavy beat IS stalled (45); the coordinator at 50 is neither (90/90).
    fake = FakeRunner()
    beat(fake, "agent-uplevel-docs", 50)
    beat(fake, "agent-uplevel-heavy", 50)
    beat(fake, "agent-uplevel-coordinator", 91)
    data = build(fake)
    docs = " ".join(sec6(data, "agent-uplevel-docs"))
    heavy = " ".join(sec6(data, "agent-uplevel-heavy"))
    coord = " ".join(sec6(data, "agent-uplevel-coordinator"))
    assert "STALE >20m" in docs and "stalled" not in docs, docs
    assert "STALE >20m" in heavy and "stalled >45m" in heavy, heavy
    assert "STALE >90m" in coord and "stalled >90m" in coord, coord


def test_a_stalled_flag_demands_silence_in_age_only():
    # UR-38's stall is age AND silence: "an agent is not stalled unless it has also pushed no
    # commit and posted no comment since." A 100-minute docs beat with a signed comment since
    # the beat is NOT stalled even though the age alone would trip the interval table. The
    # comment's first line must sign docs (head_name reads the first undecorated token;
    # `## coverage` signs nobody) and be newer than the beat -- the signed read is windowed.
    fake = FakeRunner()
    fake.repo_comments.append(comment(40, 6958, "docs · note", t(-timedelta(minutes=50))))
    beat(fake, "agent-uplevel-docs", 100)
    docs = " ".join(sec6(build(fake), "agent-uplevel-docs"))
    assert "stalled" not in docs, docs
    # and the silent arm on the same shape, so the two arms differ by one fact: an unsigned
    # comment (frontend's note signs frontend, not docs) leaves the same beat stalled.
    fake.repo_comments[-1] = comment(40, 6958, "frontend · note", t(-timedelta(minutes=50)))
    docs = " ".join(sec6(build(fake), "agent-uplevel-docs"))
    assert "stalled >90m" in docs, docs


def test_a_paused_beat_is_never_stalled_past_its_own_interval():
    # UR-160: a paused agent is not stalled -- coordinator.md routes no assignment at a paused
    # row, so §6 must not print `stalled` beside `[paused]` no matter how old the beat is. The
    # default fixture's heavy beat carries `paused` in its STATUS FIELD (the thing is_paused
    # reads, not any prose mention) and is 300 minutes old: stale, past heavy's 45-minute stall
    # table, silent (no signed comment, and _activity never even reads its activity), yet
    # flagless of `stalled`.
    fake = FakeRunner()
    beat(fake, "agent-uplevel-heavy", 300, head="heavy · paused · queue empty (ruling 88)")
    heavy = " ".join(sec6(build(fake), "agent-uplevel-heavy"))
    assert "paused" in heavy, heavy
    assert "STALE >20m" in heavy, heavy
    assert "stalled" not in heavy, heavy
    # and the row keeps no activity read at all, so a mutant that gates only on silence can
    # still see no keys -- the pinned thing is the gate's paused arm, not the fixture's shape.
    items = {h["agent"]: h for h in build(fake)["heartbeats"]["items"]}
    assert "signed_comment" not in items["agent-uplevel-heavy"]
    assert "commit_count" not in items["agent-uplevel-heavy"]


def test_a_beat_with_commits_since_it_is_not_stalled_even_unsigned():
    # UR-38's silence is BOTH arms: "pushed no commit and posted no comment". The signed-comment
    # arm is pinned above; this pins the commit arm -- a 100-minute docs beat with a commit since
    # the beat and no signed comment is NOT stalled, though the age alone trips the table. The
    # commit has to sit on a PR the lane owns (the commit leg reads the lane's own PR heads), so
    # the fixture carries the docs PR itself -- and posts NOTHING that signs docs: the default
    # repo_comments sign no docs agent, and a `docs · note` here would sign docs, flip silent
    # False under both the head and the mutant, and leave the arm untested again.
    fake = FakeRunner()
    fake.prs.append(
        {
            "number": 7050,
            "title": "docs claim",
            "isDraft": False,
            "labels": [{"name": "lane:docs"}],
            "headRefOid": "e" * 40,
            "mergeStateStatus": "BEHIND",
            "statusCheckRollup": [gate()],
        }
    )
    fake.pr_commits[7050] = [(t(-timedelta(minutes=10)), "f" * 40, "fix: the thing")]
    beat(fake, "agent-uplevel-docs", 100)
    docs = " ".join(sec6(build(fake), "agent-uplevel-docs"))
    assert "commit_count" not in docs and "1 commit(s) since the beat" in docs, docs
    assert "stalled" not in docs, docs


def test_paused_is_the_status_field_not_a_word_in_the_prose():
    # UR-160's paused flag drives §6's `[paused]` and the coordinator's routing. The substring
    # test flagged 2 of 9 live heartbeats that are not paused at all (6098014375, 6098123126 —
    # both say the word while describing someone else's lane). Defect note 6153121259 §2.
    fake = FakeRunner()
    fake.heartbeats.append(
        comment(
            6,
            6958,
            "<!-- heartbeat:agent-uplevel-frontend -->\nfrontend · 14:58Z · working #12 · "
            "heavy lane is paused per ruling 88",
            t(-timedelta(days=2)),
            t(-timedelta(minutes=7)),
        )
    )
    items = {h["agent"]: h for h in build(fake)["heartbeats"]["items"]}
    assert items["agent-uplevel-frontend"]["paused"] is False
    assert items["agent-uplevel-heavy"]["paused"] is True  # the real one still flags
    # §6 renders no body, so a `paused` flag there is unambiguous — exactly one lane earns it.
    sec6 = [ln for ln in snap.render_text(build(fake)).splitlines() if "paused" in ln]
    assert [ln.split()[0] for ln in sec6] == ["agent-uplevel-heavy"]


# --- 6b. signed activity and commits beside each beat (ruling 178/181) -----------------------


def hb(data: dict, agent: str = "agent-uplevel-backend") -> dict:
    return next(h for h in data["heartbeats"]["items"] if h["agent"] == agent)


def beat(fake: FakeRunner, agent: str, minutes: int = 6, head: str | None = None) -> None:
    """Set AGENT's live heartbeat, replacing the default fixture's row for it if there is one.

    The default carries only coordinator/backend/heavy(paused)/docs. A test about an ops or
    heavy-b row has to ask for that row: reading ``hb(data, agent)`` for an agent with no beat
    raises, and a test that guards its lookup would then certify nothing about the row it names.
    """
    tail = agent.removeprefix("agent-").removeprefix("uplevel-")
    body = f"<!-- heartbeat:{agent} -->\n{head or f'{tail} · working'}"
    row = comment(
        900 + len(fake.heartbeats), 6958, body, t(-timedelta(days=2)), t(-timedelta(minutes=minutes))
    )  # fmt: skip
    for i, c in enumerate(fake.heartbeats):
        if f"heartbeat:{agent} " in c["body"]:
            fake.heartbeats[i] = row
            return
    fake.heartbeats.append(row)


def sec6(data: dict, agent: str = "agent-uplevel-backend") -> list[str]:
    """§6's rendered lines for ONE beat: its headline plus the six-space-indented detail rows.

    Keyed by agent, not by "any line that starts with agent-uplevel-": §6 prints every agent's row,
    so a locator without a key returns the coordinator's block for a question about heavy-b.
    """
    lines = snap.render_text(data).splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.lstrip().startswith(f"{agent} "))
    block = [lines[start]]
    for ln in lines[start + 1 :]:
        if not ln.startswith("      "):
            break
        block.append(ln)
    return block


def signed(data: dict, agent: str = "agent-uplevel-backend"):
    return hb(data, agent).get("signed_comment")


def test_a_comment_leading_with_the_agents_own_name_is_its_signed_activity():
    fake = FakeRunner()
    fake.repo_comments.append(
        comment(40, 7001, "backend · 15:10Z · pushed the fix", t(-timedelta(minutes=2)), pr=True)
    )
    item = signed(build(fake))
    assert (item["id"], item["sign"]) == (40, "self")


def test_a_reviews_declared_lane_signs_it_even_when_the_lane_sits_on_line_two():
    # Ruling 178's signature rule. A review's first line is `Review: approve`; the lane name is on
    # line 2, so a first-line-only reader sees no signature at all and reports a stall.
    fake = FakeRunner()
    beat(fake, "agent-uplevel-ops-b")
    fake.repo_comments.append(
        comment(
            41,
            7001,
            "Review: approve\nReviewer lane: ops-b (cell B)\n\nPlan text: none",
            t(-timedelta(minutes=2)),
            pr=True,
        )
    )
    data = build(fake)
    assert signed(data, "agent-uplevel-ops-b")["sign"] == "self"


def test_a_review_naming_the_OTHER_cell_of_a_two_cell_lane_does_not_sign_this_one():
    # ops has two agents. An ops-b review cannot refute an ops-a stall, and reading the lane name
    # lane-wide would do exactly that: the false negative ruling 178 exists to prevent.
    fake = FakeRunner()
    beat(fake, "agent-uplevel-ops-a")
    beat(fake, "agent-uplevel-ops-b")
    fake.repo_comments.append(
        comment(
            42, 7001, "Review: approve\nReviewer lane: ops-b", t(-timedelta(minutes=2)), pr=True
        )
    )
    data = build(fake)
    assert signed(data, "agent-uplevel-ops-a") is None
    assert "activity: none signed since the beat" in " ".join(sec6(data, "agent-uplevel-ops-a"))
    assert signed(data, "agent-uplevel-ops-b")["sign"] == "self"


def test_a_lane_spelling_with_no_cell_is_reported_as_lane_named_not_signed():
    # `ops · reviewed #7001` is this lane's work but not necessarily THIS cell's. The renderer says
    # so in words, because a coordinator deciding whether to ping an agent needs the difference.
    fake = FakeRunner()
    beat(fake, "agent-uplevel-ops-b")
    fake.repo_comments.append(
        comment(43, 7001, "ops · reviewed #7001", t(-timedelta(minutes=2)), pr=True)
    )
    data = build(fake)
    item = signed(data, "agent-uplevel-ops-b")
    assert item["sign"] == "lane"
    assert "lane-named, cell not stated" in " ".join(sec6(data, "agent-uplevel-ops-b"))


def test_a_raise_ABOUT_an_agent_is_not_that_agents_activity():
    # Measured live: the coordinator's `URGENT PATH · stalled agent: agent-uplevel-heavy-b` was
    # printed as heavy-b's own signed activity, so the row said "active" beside a stall report about
    # that same agent. A bare name counts only in the AUTHOR position -- the first token of the
    # undecorated first line, which is where the role docs put an agent's identity.
    fake = FakeRunner()
    beat(fake, "agent-uplevel-heavy-b")
    fake.repo_comments.append(
        comment(
            44,
            6854,
            "**URGENT PATH · stalled agent: `agent-uplevel-heavy-b` (`6188196491`)**",
            t(-timedelta(minutes=2)),
        )
    )
    data = build(fake)
    assert signed(data, "agent-uplevel-heavy") is None


def test_the_newest_signed_comment_since_the_beat_is_the_one_printed():
    fake = FakeRunner()
    fake.repo_comments += [
        comment(50, 7001, "backend · 15:05Z · earlier", t(-timedelta(minutes=10)), pr=True),
        comment(51, 7001, "backend · 15:12Z · newest", t(-timedelta(minutes=2)), pr=True),
    ]
    assert signed(build(fake))["id"] == 51


def test_a_comment_older_than_the_beat_is_not_activity():
    # The backend beat is 30 minutes old; a comment from 40 minutes ago predates it.
    fake = FakeRunner()
    fake.repo_comments.append(
        comment(52, 7001, "backend · older than the beat", t(-timedelta(minutes=40)), pr=True)
    )
    assert signed(build(fake)) is None


def test_the_beats_prose_is_kept_for_the_lane_digest():
    data = build(FakeRunner())
    assert hb(data)["head"].startswith("backend · working")


def test_a_blocker_line_is_carried_beside_the_beat():
    fake = FakeRunner()
    beat(
        fake,
        "agent-uplevel-docs",
        minutes=4,
        head="docs · 14:59Z · working\nBLOCKER: [r165b] waits on ruling 190's gate",
    )
    data = build(fake)
    assert "ruling 190" in hb(data, "agent-uplevel-docs")["blocker"]
    assert any("BLOCKER:" in ln for ln in sec6(data, "agent-uplevel-docs"))  # rendered, not stored


def test_a_paused_agent_pays_no_activity_read():
    # UR-160: a paused agent is not stalled, so asking what it has done since its beat is not asked.
    fake = FakeRunner()
    data = build(fake)
    assert "signed_comment" not in hb(data, "agent-uplevel-heavy")
    assert not any("heavy" in ln and "activity" in ln for ln in snap.render_text(data).splitlines())


def test_the_commit_leg_reads_the_agents_own_pr_head_and_reports_the_count():
    fake = FakeRunner()
    fake.prs.append(
        {
            "number": 7050,
            "title": "backend claim",
            "isDraft": True,
            "labels": [{"name": "lane:backend"}],
            "headRefOid": "e" * 40,
            "mergeStateStatus": "BEHIND",
            "statusCheckRollup": [gate()],
        }
    )
    # The backend beat is 30 minutes old: one commit inside, one outside the window.
    fake.pr_commits[7050] = [
        (t(timedelta(minutes=-2)), "f" * 40, "fix: the thing"),
        (t(timedelta(minutes=-90)), "9" * 40, "old commit before the beat"),
    ]
    data = build(fake)
    assert hb(data)["commit_count"] == 1
    assert hb(data)["commits"][0]["subject"] == "fix: the thing"
    assert "1 commit(s) since the beat" in " ".join(sec6(data))


def test_the_commit_rows_are_capped_but_the_count_is_not():
    # §6 prints at most three rows per agent because the report is what a coordinator reads in one
    # pass; the NUMBER underneath stays whole, or "3 commit(s)" would understate a busy lane.
    fake = FakeRunner()
    fake.prs.append(
        {
            "number": 7050,
            "title": "backend claim",
            "isDraft": True,
            "labels": [{"name": "lane:backend"}],
            "headRefOid": "e" * 40,
            "mergeStateStatus": "BEHIND",
            "statusCheckRollup": [gate()],
        }
    )
    fake.pr_commits[7050] = [
        (t(timedelta(minutes=-m)), f"{m}" * 40, f"commit {m}") for m in (2, 5, 9, 20)
    ]
    data = build(fake)
    block = sec6(data)
    assert hb(data)["commit_count"] == 4
    assert len([ln for ln in block if " commit #" in ln]) == 3
    assert "4 commit(s) since the beat (1 more)" in " ".join(block)
    # The three kept are the three NEWEST (oldest-first, so they read chronologically), not the
    # first three the log walked back to -- which for `git log` is the opposite end.
    assert [c["subject"] for c in hb(data)["commits"]] == ["commit 9", "commit 5", "commit 2"]


def test_a_pr_labelled_lane_only_on_a_two_cell_lane_is_listed_for_neither_cell():
    # rules.md:92-93: ops has two cells; `lane:ops` with no `cell:` is genuinely ambiguous. Printing
    # it under one cell would credit the other agent's push to this one, so §6 names it as
    # uncellated beside each ops beat instead of guessing.
    fake = FakeRunner()
    fake.prs.append(
        {
            "number": 7159,
            "title": "unlabelled cell",
            "isDraft": True,
            "labels": [{"name": "lane:ops"}],
            "headRefOid": "1" * 40,
            "mergeStateStatus": "BEHIND",
            "statusCheckRollup": [gate()],
        }
    )
    beat(fake, "agent-uplevel-ops-a")
    data = build(fake)
    assert hb(data, "agent-uplevel-ops-a")["uncellated_prs"] == [7159]
    assert "uncellated ops PR(s), either cell: #7159" in snap.render_text(data)


def test_a_heavy_pr_without_the_heavy_b_cell_is_heavy_a_s():
    # rules.md's own tie-break: `cell:heavy-b` is heavy-b's, every other heavy PR heavy-a's.
    assert snap.owner_of_pr(["heavy"]) == ("heavy", "a", True)
    assert snap.owner_of_pr(["heavy", "cell:heavy-b"]) == ("heavy", "b", True)
    assert snap.owner_of_pr(["lane:ops", "cell:b"]) == ("ops", "b", True)
    assert snap.owner_of_pr(["lane:ops"]) == ("ops", None, False)
    assert snap.owner_of_pr(["review:ops-b"]) is None  # a review label routes, it does not own


def test_the_activity_extra_read_is_paid_only_when_a_beat_predates_the_comment_window():
    # §2 fetched comments since the cursor (14:30Z). The backend beat is 30 min old (14:30Z), so the
    # window already covers it and the read is free. A beat older than the cursor would make §2's
    # items incomplete, and printing "no activity" from an unread window is a false stall.
    fake = FakeRunner()
    build(fake)
    extra = [c[2] for c in fake.calls if c[:2] == ["gh", "api"] and "/issues/comments?" in c[2]]
    assert len(extra) == 1  # §2's read only


def test_a_beat_older_than_the_cursor_pays_one_comment_read_from_its_own_beat():
    fake = FakeRunner()
    fake.heartbeats[1] = comment(
        2,
        6958,
        "<!-- heartbeat:agent-uplevel-backend -->\nbackend · working",
        t(-timedelta(days=2)),
        t(-timedelta(minutes=90)),  # 13:30Z, an hour before the 14:30Z cursor
    )
    build(fake)
    reads = [c[2] for c in fake.calls if c[:2] == ["gh", "api"] and "/issues/comments?" in c[2]]
    assert len(reads) == 2
    assert f"since={t(timedelta(minutes=-90))}" in reads[1]


def test_a_failing_activity_read_is_reported_and_the_silence_is_labelled():
    fake = FakeRunner()
    fake.heartbeats[1] = comment(
        2,
        6958,
        "<!-- heartbeat:agent-uplevel-backend -->\nbackend · working",
        t(-timedelta(days=2)),
        t(-timedelta(minutes=90)),
    )
    fake.rules["issues/comments?since=2026-10-13T13:30"] = snap.CommandError("HTTP 502")
    data = build(fake)
    assert any("activity since" in e for e in data["heartbeats"]["errors"])


def test_a_failing_commit_read_names_the_pr_instead_of_reporting_zero_commits():
    # "0 commits since the beat" is a stall signal. An unread log must never print that number.
    fake = FakeRunner()
    fake.prs.append(
        {
            "number": 7050,
            "title": "backend claim",
            "isDraft": True,
            "labels": [{"name": "lane:backend"}],
            "headRefOid": "e" * 40,
            "mergeStateStatus": "BEHIND",
            "statusCheckRollup": [gate()],
        }
    )
    fake.fail("git log")
    data = build(fake)
    assert hb(data)["commit_errors"]
    assert not hb(data)["commits"]
    assert "ERROR commits:" in " ".join(sec6(data))


# --- robustness and read-only ---------------------------------------------------------------


def test_a_gh_failure_in_one_section_leaves_the_others(capsys):
    fake = FakeRunner()
    fake.fail("gh pr list")
    assert snap.main([], fake, lambda: NOW) == 0
    out = capsys.readouterr().out
    assert "ERROR prs: HTTP 504" in out
    assert "agent-uplevel-backend" in out
    assert "BINDING NOW · live one" in out
    assert sum(1 for c in fake.calls if c[:3] == ["gh", "pr", "list"]) == 2


def test_a_failed_heartbeat_read_still_reads_comments_from_the_fallback_cursor():
    fake = FakeRunner()
    fake.fail("/issues/6958/comments")
    data = build(fake)
    assert data["cursor"]["errors"] == ["HTTP 504"]
    assert data["cursor"]["cursor"] == "2026-10-13T13:00:00Z"
    assert data["heartbeats"]["errors"] == ["HTTP 504"]
    assert data["comments"]["items"]


def test_the_script_never_writes_to_github():
    fake = FakeRunner()
    build(fake)
    for cmd in fake.calls:
        assert "-X" not in cmd and "--method" not in cmd
        assert cmd[:2] in (["gh", "api"], ["gh", "run"], ["gh", "pr"], ["git", "fetch"]) or (
            cmd[0] == "git"
        )
        if cmd[:2] == ["gh", "pr"]:
            # read subcommands only — list (the batch) and view (a capped-rollup re-read)
            assert cmd[2] in ("list", "view")


def test_paginated_pages_are_flattened():
    assert snap.parse_json_stream('[1, 2]\n[3]\n{"a": 1}') == [1, 2, 3, {"a": 1}]
    assert snap.parse_json_stream("") == []


def test_text_report_has_the_six_sections_in_order():
    text = snap.render_text(build(FakeRunner()))
    heads = [line for line in text.splitlines() if line.startswith("== ")]
    assert [h.split(".")[0] for h in heads] == [
        "== 1", "== 2", "== 3", "== 4", "== 5", "== 6", "== 7", "== 8",
    ]  # fmt: skip
    assert "merge without update-branch: yes" in text


# --- 7. ruling 164: UR-106 hashes, the disable list, the merged audit ----------------------

APPROVED_DIFF = (
    "diff --git a/docs/b.md b/docs/b.md\n"
    "index abc1234..def5678 100644\n"
    "--- a/docs/b.md\n"
    "+++ b/docs/b.md\n"
    "@@ -1,3 +1,9 @@\n"
    " context line\n"
    "+added line\n"
)
CARRY_DIFF = APPROVED_DIFF.replace("@@ -1,3 +1,9 @@", "@@ -1,3 +1,12 @@").replace(
    "index abc1234..def5678", "index abc1234..9f8e7d6"
)  # an update-branch roll: a new blob pair and shifted hunk numbers, no body change
COMMIT_DIFF = APPROVED_DIFF + (
    "diff --git a/docs/extra.md b/docs/extra.md\n"
    "new file mode 100644\n"
    "index 0000000..1111111\n"
    "--- /dev/null\n"
    "+++ b/docs/extra.md\n"
    "@@ -0,0 +1 @@\n"
    "+author commit\n"
)
APPROVED_HEAD = "abc1234" + "0" * 33  # the sha the review comment names, 7-hex prefix abc1234
APPROVED_BASE = "d" * 40  # the approved head's own merge-base -- older than the roll's base
MERGE_MAIN = "1" * 40  # the merge commit's first parent: main as it stood at the merge
MERGE_PARENT = "a" * 40  # the merged PR's head, second parent of the merge commit
LANDED_OTHER = "c" * 40  # a merged head that is not the approved head


def shell_ur106_hash(diff: str) -> str:
    """``roles/coordinator.md``'s pipeline, run for real, as the definition of the hash.

    The shell string here IS the rule's text, copied from §Merging a PR step 2 — rewriting it as
    argv would replace the thing under test with my own paraphrase of it. The pipeline is
    constant (no interpolation), and the ``returncode`` assert below keeps a broken ``grep``/``sed``
    from reading as agreement.
    """
    got = subprocess.run(  # noqa: S602, PLW1510  # nosemgrep: shell-injection
        # The pipeline is the rule's own text and reading its returncode by hand is the point
        # (a broken grep must not read as agreement). The command is a constant with no
        # interpolation and the diff arrives on stdin, so nothing can be placed in the shell.
        "grep -v '^index ' | sed 's/^@@ .* @@/@@/' | sha256sum | cut -d' ' -f1",
        shell=True,
        input=diff.encode(),
        capture_output=True,
    )
    assert got.returncode == 0, got.stderr.decode()
    return got.stdout.decode().strip()


def named(rev: str) -> str:
    """The string a review comment names for ``rev`` -- git resolves the abbreviation itself.

    Reviews name 7-hex prefixes (the shipped verdict convention: ``Head reviewed: `a1b2c3d```),
    and the implementation interpolates the named string straight into ``merge-base``/``diff``
    because git resolves an unambiguous abbreviation natively -- UR-106's prose pipeline never
    sees a full sha either. So the fake's git answers are keyed by this, not by the full sha.
    """
    return rev[:7]


def _recorded_reads(fake: FakeRunner, head_diff: str) -> FakeRunner:
    """The UR-106 reads for #7001: head diff at its own base, approved-head diff at its own base.

    The two ranges use two different bases on purpose. A base roll moves ``merge-base
    origin/main <rev>``, and the rolled base is not an ancestor of the *old* approved sha, so
    hashing both revs against today's merge-base would report ``carry: no`` for a roll that
    carries. Each rev is hashed against its own merge-base.
    """
    fake.own_diffs[f"{BASE}..{HEAD}"] = head_diff
    fake.own_diffs[f"{APPROVED_BASE}..{APPROVED_HEAD}"] = APPROVED_DIFF
    fake.merge_bases[f"origin/main::{APPROVED_HEAD}"] = APPROVED_BASE
    return fake


def _approved_not_head(fake: FakeRunner) -> FakeRunner:
    fake.reviews = [
        {
            "id": 30,
            "created_at": t(-timedelta(hours=2)),
            "user": "ops-b",
            "body": f"Review: approve\nHead: `{APPROVED_HEAD[:7]}`",
        }
    ]
    return fake


def test_the_hash_equals_the_prose_pipeline_of_coordinator_md():
    """roles/coordinator.md's `grep -v '^index ' | sed 's/^@@ .* @@/@@/' | sha256sum`, run for
    real over the same bytes, is the definition the script must match -- prose and code cannot
    drift while this test runs the prose itself."""
    want = shell_ur106_hash(APPROVED_DIFF)
    assert snap.ur106_diff_hash(APPROVED_DIFF) == want
    # a roll changes nothing for it, an author commit changes everything:
    assert snap.ur106_diff_hash(CARRY_DIFF) == want
    assert snap.ur106_diff_hash(COMMIT_DIFF) != want
    assert hashlib.sha256.__name__  # the same primitive, not a truncation of it


@pytest.mark.parametrize(
    "diff",
    [
        # two hunks of two files: the shape a real PR's own diff has, not the toy above
        "diff --git a/x b/x\nindex 1..2 100644\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n"
        "@@ -9 +9 @@ def f():\n c\n+d\n"
        "diff --git a/y b/y\nnew file mode 100644\nindex 0..3 100644\n--- /dev/null\n"
        "+++ b/y\n@@ -0,0 +1,2 @@\n+e\n+f\n",
        # a hunk header whose function context itself contains "@@", which is what makes sed's
        # leftmost-longest match worth pinning against Python's greedy `.*`
        "@@ -1,2 +1,2 @@ x @@ -3,4 +3,4 @@\n ctx\n+line\n",
        # an ADDED line that starts with "index ": sed anchors ^index on the line, whose first
        # character is the diff's "+", so it survives -- a substring filter would eat it
        "@@ -1 +1 @@\n ctx\n+index of the thing\n",
        # CRLF, which git quotes as-is; sha256sum hashes the bytes it is handed
        "@@ -1 +1 @@\r\n ctx\r\n+added\r\n",
    ],
    ids=["two-files", "double-at-in-context", "added-index-line", "crlf"],
)
def test_the_hash_matches_the_pipeline_on_adversarial_diffs(diff: str):
    """One agreeing diff could hide a filter that diverges on another shape, and a divergent
    filter changes a recorded hash -- which reads as `carry: no` on a PR that carried, blocking
    an owner merge the rule says to allow. So the shapes that could split prose from code."""
    want = shell_ur106_hash(diff)
    assert want, "the pipeline ran (an empty answer means the fixture is not reaching sed)"
    assert snap.ur106_diff_hash(diff) == want


def test_own_diff_carry_yes_on_a_base_roll():
    fake = _approved_not_head(_recorded_reads(FakeRunner(), CARRY_DIFF))
    p = pr(build(fake))
    assert p["own_diff"]["head"] == snap.ur106_diff_hash(CARRY_DIFF)
    assert p["own_diff"]["approved"] == snap.ur106_diff_hash(APPROVED_DIFF)
    assert p["own_diff"]["carry"] is True
    assert any("carry=yes" in line for line in rendered_pr_block(build(fake)))


def test_own_diff_carry_no_on_an_author_commit():
    fake = _approved_not_head(_recorded_reads(FakeRunner(), COMMIT_DIFF))
    data = build(fake)
    p = pr(data)
    assert p["own_diff"]["carry"] is False
    assert any("carry=no" in line for line in rendered_pr_block(data))


def test_own_diff_reads_scope_to_pr_files_and_use_two_ranges():
    fake = _approved_not_head(_recorded_reads(FakeRunner(), COMMIT_DIFF))
    build(fake)
    diffs = [c for c in fake.calls if c[:2] == ["git", "diff"] and "--" in c]
    assert [c[2] for c in diffs] == [f"{BASE}..{HEAD}", f"{APPROVED_BASE}..{named(APPROVED_HEAD)}"]
    for c in diffs:
        assert c[3] == "--" and c[4:] == ["docs/b.md"], "UR-106 hashes the OWN diff, not the tree"


def test_an_approval_naming_the_head_needs_one_read_and_carries():
    fake = FakeRunner()  # the base fixture's review names a1b2c3d == HEAD[:7]
    fake.own_diffs[f"{BASE}..{HEAD}"] = APPROVED_DIFF
    p = pr(build(fake))
    assert p["own_diff"]["carry"] is True
    assert p["own_diff"]["approved"] == p["own_diff"]["head"]


def test_drafts_get_no_own_diff_reads():
    data = build(FakeRunner())
    p = pr(data, 7002)
    assert "own_diff" not in p


def test_a_failed_own_diff_read_reports_carry_unknown():
    fake = _approved_not_head(_recorded_reads(FakeRunner(), COMMIT_DIFF))
    fake.fail(f"{APPROVED_BASE}..{named(APPROVED_HEAD)}", "fatal: bad object")
    data = build(fake)
    p = pr(data)
    assert p["own_diff"]["carry"] is None
    assert p["own_diff"]["approved"] is None
    assert any("own-diff" in e for e in p["errors"])


def _armed():
    return {"enabledAt": t(-timedelta(hours=1)), "mergeMethod": "MERGE"}


def test_disable_list_flags_an_armed_uncarried_head():
    fake = _approved_not_head(_recorded_reads(FakeRunner(), COMMIT_DIFF))
    fake.prs[0]["autoMergeRequest"] = _armed()
    data = build(fake)
    watch = data["auto_merge_watch"]
    assert watch["disable"] == [7001]
    assert watch["ok"] == [] and watch["unknown"] == []
    text = snap.render_text(data)
    assert "auto-merge to disable: #7001" in text


def test_armed_on_the_approved_head_is_ok():
    fake = FakeRunner()
    fake.own_diffs[f"{BASE}..{HEAD}"] = APPROVED_DIFF
    fake.prs[0]["autoMergeRequest"] = _armed()
    data = build(fake)
    assert data["auto_merge_watch"]["ok"] == [7001]
    assert data["auto_merge_watch"]["disable"] == []


def test_armed_on_a_carried_head_is_ok_too():
    fake = _approved_not_head(_recorded_reads(FakeRunner(), CARRY_DIFF))
    fake.prs[0]["autoMergeRequest"] = _armed()
    data = build(fake)
    assert data["auto_merge_watch"]["ok"] == [7001]
    assert data["auto_merge_watch"]["disable"] == []


def test_an_armed_head_whose_carry_is_unknown_is_never_told_to_disable():
    fake = _approved_not_head(_recorded_reads(FakeRunner(), COMMIT_DIFF))
    fake.fail(f"{APPROVED_BASE}..{named(APPROVED_HEAD)}", "fatal: bad object")
    fake.prs[0]["autoMergeRequest"] = _armed()
    data = build(fake)
    assert data["auto_merge_watch"]["disable"] == []
    assert data["auto_merge_watch"]["unknown"] == [7001]


def merge_sha(number: int) -> str:
    """The merge commit of PR <number>, derived from its number so tests need no table."""
    return (f"{number:x}" + "0" * 36)[-40:]


def landed_sha(number: int) -> str:
    """The head PR <number> landed: the merge commit's second parent.

    Derived from the number because a PR's head is not the merge commit and two merged PRs
    cannot land the same commit, so every merge needs its own sha.
    """
    return "2" + merge_sha(number)[1:]


def base_of(rev: str) -> str:
    """The merge-base this fake resolves for one rev -- per rev, not one shared base."""
    return f"{rev[:6]}b" + "0" * 33


def merged(number, minutes, body=""):
    """One row of the REST merged list, which carries ``body`` (verified against the wire)."""
    return {"number": number, "title": f"PR {number}", "merged_at": t(-timedelta(minutes=minutes)),
            "merge_commit_sha": merge_sha(number), "body": body}  # fmt: skip


def review_on(fake, number, sha, cid=900):
    fake.pr_issue_comments.setdefault(number, []).append(
        comment(cid, number, f"Review: approve\nHead: `{sha[:7]}`", t(-timedelta(hours=3)), pr=True)
    )


def merge_of(fake, number, *diffs, approved=None, files=("docs/b.md",)):
    """Wire the git reads for one merged PR and return its landed head.

    The landed head is the merge commit's second parent and the base root is its first parent
    (main at the merge). The live merge-base of a merged head *is* the head, so hashing from it
    yields an empty diff and every carry check passes for free -- the base must come from the
    merge commit. ``diffs`` are the own diffs of [approved, landed], at their own bases, so a
    PR approved at its own head takes one diff and a carried one takes two.
    """
    row = next(p for p in fake.merged_prs if p["number"] == number)
    landed = landed_sha(number)
    approved = landed if approved is None else approved
    fake.parents[row["merge_commit_sha"]] = (MERGE_MAIN, landed)
    fake.pr_files_by_number[number] = list(files)
    for rev, diff in zip(([approved] if approved == landed else [approved, landed]), diffs, strict=True):  # fmt: skip
        fake.merge_bases[f"{MERGE_MAIN}::{rev}"] = base_of(rev)
        fake.own_diffs[f"{base_of(rev)}..{rev}"] = diff
    return landed


def owner_words(fake, body, cid=99):
    """A comment in the owner's *voice* -- the shape, not the account.

    One GitHub account posts everything in this programme (memory
    shared-token-pr-ownership-not-author), so ``user`` carries no signal and is left at its
    default on purpose. UR-45 is what distinguishes: only the owner writes "RULING"; the
    coordinator writes an unnumbered "coordinator decision" and the status comment says "no
    owner ruling names this PR" -- so an unmarked mention must not bar, or the bar cries wolf.
    """
    fake.owner_comments.append(comment(cid, 6854, body, t(-timedelta(minutes=10))))


def test_merged_audit_verdicts_and_the_prefilled_ur29_comment():
    fake = FakeRunner()
    fake.merged_prs = [
        merged(7100, 25),  # approved at the landed head: ok
        merged(7101, 24),  # no approving review at all
        merged(7102, 23),  # approved at another head, landed as a carry
        merged(7103, 22, "## Done when\n\nNotes: owner: do not merge, held for ruling 188.\n"),
    ]
    review_on(fake, 7100, landed_sha(7100))
    merge_of(fake, 7100, APPROVED_DIFF)
    review_on(fake, 7102, LANDED_OTHER)  # approved at LANDED_OTHER, landed as something else
    merge_of(fake, 7102, APPROVED_DIFF, CARRY_DIFF, approved=LANDED_OTHER)
    review_on(fake, 7103, landed_sha(7103))
    merge_of(fake, 7103, APPROVED_DIFF)
    data = build(fake)
    audit = {i["number"]: i for i in data["merged_audit"]["items"]}
    assert audit[7100]["verdict"] == "ok"
    assert audit[7101]["verdict"] == "no approving review"
    assert audit[7102]["verdict"] == "ok (UR-106 carry)"
    assert audit[7103]["verdict"].startswith("BARRED by owner")
    assert "do not merge" in audit[7103]["verdict"]
    text = audit[7100]["merge_comment"]
    assert text.startswith("Merged #7100")
    assert "no owner ruling names this PR" in text
    assert f"`{audit[7100]['merge'][:9]}`" in text
    assert data["merged_audit"]["since"] == data["cursor"]["cursor"]


def test_a_merged_head_that_is_neither_approved_nor_a_carry_is_bared():
    """The whole point of the audit: an auto-merge that landed a head nobody approved."""
    fake = FakeRunner()
    fake.merged_prs = [merged(7108, 18)]
    review_on(fake, 7108, LANDED_OTHER)
    merge_of(fake, 7108, APPROVED_DIFF, COMMIT_DIFF, approved=LANDED_OTHER)
    data = build(fake)
    audit = {i["number"]: i for i in data["merged_audit"]["items"]}
    assert audit[7108]["verdict"].startswith("NOT APPROVED at the landed head")
    assert audit[7108]["carry"] is False
    assert any("#7108" in line for line in snap.render_text(data).splitlines())


def test_merged_audit_skips_merges_at_or_before_the_cursor():
    fake = FakeRunner()
    fake.merged_prs = [merged(7100, 90)]  # cursor is t(-30m)
    data = build(fake)
    assert data["merged_audit"]["items"] == []
    # Both spellings of the read are covered: a bare `"pulls/7100" in calls` could never match a
    # `gh pr view 7100 --repo o/r` argv list, so it would pass for the wrong reason.
    per_pr = [c for c in fake.calls if "pulls/7100" in " ".join(c) or "pr view 7100" in " ".join(c)]
    assert per_pr == [], f"a skipped merge still cost reads: {per_pr}"


def test_merged_audit_reads_the_own_diff_at_the_merge_not_the_live_head():
    """A merged PR's approved-vs-landed diff is vacuous after the merge (the head is an ancestor
    of the merge commit), so it is measured at the merge commit's parents."""
    fake = FakeRunner()
    fake.merged_prs = [merged(7102, 23)]
    review_on(fake, 7102, LANDED_OTHER)
    landed = merge_of(fake, 7102, APPROVED_DIFF, CARRY_DIFF, approved=LANDED_OTHER)
    build(fake)
    ranges = [c[2] for c in fake.calls if c[:2] == ["git", "diff"] and "--" in c]
    assert len(ranges) == 2 and all(".." in r for r in ranges)
    assert ranges[1].endswith(f"..{landed}"), "the second hash is of the landed head"
    assert all(not r.startswith("origin/main") for r in ranges), "never from the live merge-base"


def test_the_prefilled_comment_names_what_it_did_not_read():
    """UR-29 wants each check's conclusion quoted. The audit runs after an auto-merge, so the
    snapshot never read the checks -- the draft must mark that gap, not print a clean comment
    that reads as if the evidence were complete (UR-154)."""
    fake = FakeRunner()
    fake.merged_prs = [merged(7100, 25)]
    review_on(fake, 7100, landed_sha(7100))
    merge_of(fake, 7100, APPROVED_DIFF)
    data = build(fake)
    text = {i["number"]: i for i in data["merged_audit"]["items"]}[7100]["merge_comment"]
    assert "checks: unread" in text
    assert "success" not in text.lower(), "no invented check conclusion"


def test_an_unreachable_approved_rev_reports_unknown_rather_than_ok():
    """A gc'd or force-pushed-away approved rev fails the read. Reading that as a carry (or
    skipping the check because a hash came back None) would print 'ok' on a head nobody
    approved."""
    fake = FakeRunner()
    fake.merged_prs = [merged(7105, 20)]
    review_on(fake, 7105, LANDED_OTHER)
    merge_of(fake, 7105, APPROVED_DIFF, CARRY_DIFF, approved=LANDED_OTHER)
    # A deleted key would raise AssertionError from the fake, which production never does: the
    # real runner raises CommandError, so the read has to fail the way a gc'd rev fails it.
    fake.fail(f"{base_of(LANDED_OTHER)}..{named(LANDED_OTHER)}", "fatal: bad object")
    data = build(fake)
    audit = {i["number"]: i for i in data["merged_audit"]["items"]}
    assert audit[7105]["verdict"].startswith("unknown")
    assert audit[7105]["carry"] is None


def test_an_owner_record_naming_the_pr_bars_it_without_a_body_hit():
    fake = FakeRunner()
    fake.merged_prs = [merged(7104, 21)]
    review_on(fake, 7104, landed_sha(7104))
    merge_of(fake, 7104, APPROVED_DIFF)
    owner_words(fake, "RULING #6854: do not merge #7104 pending the audit")
    data = build(fake)
    audit = {i["number"]: i for i in data["merged_audit"]["items"]}
    assert audit[7104]["verdict"].startswith("BARRED by owner")
    assert "#7104" in audit[7104]["verdict"]


def test_an_owner_record_about_another_pr_does_not_bar_this_one():
    """The bar matches on the PR number, so #7104's hold must not smear onto #7109."""
    fake = FakeRunner()
    fake.merged_prs = [merged(7109, 17)]
    review_on(fake, 7109, landed_sha(7109))
    merge_of(fake, 7109, APPROVED_DIFF)
    owner_words(fake, "RULING #6854: do not merge #7104 pending the audit")
    data = build(fake)
    audit = {i["number"]: i for i in data["merged_audit"]["items"]}
    assert audit[7109]["verdict"] == "ok"


def test_an_unmarked_mention_of_the_pr_on_6854_does_not_bar_it():
    """The coordinator's own status comment on #6854 names open PRs, and UR-29 makes it say
    "no owner ruling names this PR" -- written from the SAME account as the owner's rulings
    (memory shared-token-pr-ownership-not-author). So the bar keys on the owner's shape, never
    on the author, or every audited merge would be flagged every tick."""
    fake = FakeRunner()
    fake.merged_prs = [merged(7106, 19)]
    review_on(fake, 7106, landed_sha(7106))
    merge_of(fake, 7106, APPROVED_DIFF)
    fake.owner_comments.append(
        comment(
            98,
            6854,
            "<!-- status:uplevel-coordinator -->\n#7106 merged; no owner ruling names this PR",
            t(-timedelta(minutes=10)),
        )
    )
    data = build(fake)
    audit = {i["number"]: i for i in data["merged_audit"]["items"]}
    assert audit[7106]["verdict"] == "ok"


# --- 8. ruling 164: the status comment drafted from the snapshot ---------------------------

DRAFT_SCRIPT = REPO_ROOT / "scripts" / "uplevel" / "status_draft.py"


def _load_status_draft():
    spec = importlib.util.spec_from_file_location("status_draft", DRAFT_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["status_draft"] = mod
    spec.loader.exec_module(mod)
    return mod


def _status_scenario(fake: FakeRunner) -> FakeRunner:
    """A base scenario plus what part 9 counts: two merges, both after the newest owner record.

    The default owner comments put the newest one at t-2h; the merges at t-25m and t-90m are
    both inside that window, and the newest is an "Owner record", not a BINDING NOW record --
    UR-166's part 9 counts merges since either.
    """
    fake.merged_prs = [merged(7100, 25), merged(7107, 90)]
    for row in fake.merged_prs:
        fake.parents[row["merge_commit_sha"]] = (MERGE_MAIN, MERGE_PARENT)
    return fake


def test_status_draft_holds_ur166s_order_and_its_marker():
    sd = _load_status_draft()
    body = sd.render(build(_status_scenario(FakeRunner())), questions=[])
    assert body.startswith(sd.MARKER), "part 1 finds the comment by its first line"
    order = [
        "BINDING NOW",
        "== main",
        "== Questions for the owner",
        "== Owner tier awaiting approval",
        "== Real-tier runs for the owner",
        "== Status rows owed",
        "== Stalled and stale heartbeats",
        "== Queue",
        "== Counts",
    ]
    at = [body.find(head) for head in order]
    assert -1 not in at, [h for h, i in zip(order, at, strict=True) if i < 0]
    assert at == sorted(at), "UR-166 fixes the order; a reordered comment re-reads as churn"


def test_status_draft_lists_every_open_pr_drafts_included():
    sd = _load_status_draft()
    body = sd.render(build(FakeRunner()), questions=[])
    assert "#7101" not in body  # nothing outside the snapshot's own PRs
    for number, draft_flag in ((7001, False), (7002, True)):
        line = next(ln for ln in body.splitlines() if f"#{number} " in ln)
        assert ("draft" if draft_flag else "ready") in line


def test_an_empty_questions_section_says_so_loudly():
    """UR-166's part 3 is the one the owner reads first. Silence and 'nothing to ask' look the
    same in a rendered comment, so an empty list prints a placeholder, never a bare heading."""
    sd = _load_status_draft()
    body = sd.render(build(FakeRunner()), questions=[])
    section = body.split("== Questions for the owner", 1)[1].split("\n== ", 1)[0]
    assert sd.NO_QUESTIONS in section
    assert body.count(sd.NO_QUESTIONS) == 1, "one placeholder, not a paragraph of prose"


def test_questions_are_written_verbatim_in_order():
    sd = _load_status_draft()
    body = sd.render(
        build(FakeRunner()), questions=["a. jump the queue? (rec: no)", "b. park F2.3?"]
    )
    assert "a. jump the queue? (rec: no)" in body
    assert body.index("a. jump the queue") < body.index("b. park F2.3")


def test_overlong_drafts_are_reported_not_silently_truncated():
    """UR-166 says about 4,000 characters. Truncating would drop part 9 and leave the owner with
    a partial report that looks complete, so the function returns the length and keeps the body."""
    sd = _load_status_draft()
    short = sd.render(build(FakeRunner()), questions=[])
    assert sd.over_limit(short) is None
    long = sd.render(build(FakeRunner()), questions=[f"q{i}. " + "x" * 200 for i in range(30)])
    assert len(long) > sd.LIMIT
    assert sd.over_limit(long) == len(long) - sd.LIMIT
    assert long.rstrip().splitlines()[-1].startswith("== Counts"), (
        "an overlong body keeps part 9 last -- it is trimmed by hand, never cut from the end"
    )


def test_part_nine_counts_merges_since_the_newest_owner_record_including_auto_merged():
    sd = _load_status_draft()
    data = build(_status_scenario(FakeRunner()))
    body = sd.render(data, questions=[])
    counts = body.split("== Counts", 1)[1]
    assert "open programme PRs: 2" in counts
    assert "merged since the newest owner record: 2" in counts


def test_the_audit_window_and_the_count_window_are_different_on_purpose():
    """UR-166 part 9 counts merges since the newest OWNER RECORD; step 12 audits merges since the
    CURSOR. #7107 sits between the two, so a naive implementation that reuses one filtered list
    gets one of the two numbers wrong -- and both look plausible."""
    sd = _load_status_draft()
    data = build(_status_scenario(FakeRunner()))
    assert [i["number"] for i in data["merged_audit"]["items"]] == [7100]
    counts = sd.render(data, questions=[]).split("== Counts", 1)[1]
    assert "merged since the newest owner record: 2" in counts
