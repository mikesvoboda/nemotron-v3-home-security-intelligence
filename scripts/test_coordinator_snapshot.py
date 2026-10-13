#!/usr/bin/env python3
"""Tests for scripts/uplevel/coordinator_snapshot.py (ruling 152), with no network.

Run explicitly; outside testpaths (like every scripts/test_*.py gate suite):

    uv run python -m pytest scripts/test_coordinator_snapshot.py -q

Every gh and git call the script makes goes through one runner; these tests pass a fake that
answers by command shape and records what was asked, and a fixed clock. Each test changes one
answer of a shared green scenario, so a passing arm and a failing arm differ by one fact.
"""

from __future__ import annotations

import importlib.util
import json
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
                return json.dumps(self.repo_comments)
            if "/issues/7001/comments" in path:
                return json.dumps(self.reviews)
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
            rollup = self.pr_rollups.get(number)
            if rollup is None:  # the fake's batched answer, as if the cap never bit
                rollup = next(p["statusCheckRollup"] for p in self.prs if p["number"] == number)
            return json.dumps({"statusCheckRollup": rollup})
        if cmd[:2] == ["git", "fetch"]:
            return ""
        if cmd[:2] == ["git", "rev-parse"]:
            return TIP + "\n"
        if cmd[:2] == ["git", "merge-base"]:
            return BASE + "\n"
        if cmd[:2] == ["git", "rev-list"]:
            return self.merges_behind[cmd[-1].split("..")[0]] + "\n"
        if cmd[:2] == ["git", "diff"]:
            if cmd[-1] == "origin/main":
                return self.main_files[cmd[-2]]
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
    assert [h.split(".")[0] for h in heads] == ["== 1", "== 2", "== 3", "== 4", "== 5", "== 6"]
    assert "merge without update-branch: yes" in text
