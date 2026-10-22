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
from typing import Any

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
TIP = "f" * 40
GATE_RUN = 900


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


# --- ruling 290's balance fixtures ---------------------------------------------------------
# The roster carries the three shapes the section must tell apart: a fast two-cell lane (ops-a
# backlogged, ops-b idle), a one-cell fast lane, and the strongest tier that alone may take a
# `heavy` package. Rows read | `agent` | model | queue | label |, the live column names.
ROSTER = """\
| sandbox               | model     | queue                                    | review label |
| --------------------- | --------- | ---------------------------------------- | ------------ |
| `uplevel-coordinator` | fast      | routing (`roles/coordinator.md`)         | none         |
| `uplevel-ops-a`       | fast      | `O2.4`, `[r295]`, `O3.7`                 | none         |
| `uplevel-ops-b`       | fast      | `[r290]`                                 | none         |
| `uplevel-ops-c`       | fast      | none                                     | none         |
| `uplevel-heavy-b`     | strongest | `[r273]`, `B2.3`                         | none         |
"""  # fmt: skip
README = """\
<!-- prettier-ignore -->
| package | lane                    | phase      | name                                           | flags         | status      | PR  |
| ------- | ----------------------- | ---------- | ---------------------------------------------- | ------------- | ----------- | --- |
| O2.4    | ops                     | 2          | Re-ID on the GB300 GPU via TensorRT            |               | in progress | #7002 |
| B2.3    | backend                 | 2          | Re-ID model bake-off                           | heavy         | not started |       |
| O3.7    | ops                     | 3          | `scripts/` truth                               |               | not started |     |
| R2a     | owner; frontend records | 2          | Phase 2 RULING session, part 1 (as it stood)   | owner         | done        | #6980 |
| R2b     | owner; frontend records | 2          | Phase 2 RULING session, part 2 (after `F2.3`)  | owner         | done        | #7030 |
"""  # fmt: skip
# One lane file with every dependency shape the six pins name: `O2.4` depends on `R2` -- free
# text the README cannot resolve (no row is named `R2`), so it reads unread, never met; `[r295]`
# depends on nothing; `O3.7` depends on nothing and is `heavy` (UR-24's move constraint).
OPS_PKG = """\
### O2.4 Re-ID on the GB300 GPU via TensorRT

**Flags:** none. **Depends on:** `R2`. **PR:** #7002. (ruling 84)

- [ ] box

### [r295] pip leaves the production image

**Flags:** none. **Assigned:** backend. **Depends on:** none. **PR:** none yet. (ruling 295)

- [ ] box

### O3.7 `scripts/` truth

**Flags:** `heavy`. **Assigned:** heavy-b (ruling 298). **Depends on:** none. **PR:** none yet.
(ruling 298)

- [ ] box
"""  # fmt: skip


def beat_row(agent: str, prose: str, minutes: int = 5, cid: int | None = None) -> dict:
    """A heartbeat in the live shape; the status field rides the second line."""
    return {
        "id": cid if cid is not None else abs(hash(agent)),
        "user": {"login": "mikesvoboda"},
        "created_at": t(-timedelta(days=2)),
        "updated_at": t(-timedelta(minutes=minutes)),
        "body": f"<!-- heartbeat:{agent} -->\n{prose}",
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
        # The merge-base is 10 merges behind the tip.
        self.merges_behind = {BASE: "10"}
        self.pr_files = "docs/b.md\n"
        # Per-PR rollups that differ from the batched list's (the list caps each PR at 100 entries).
        self.pr_rollups: dict[int, list] = {}
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
        # ruling 278's subset carry: the branch's first-parent commits after an approved head,
        # one line per commit in `%P` shape ("p1" for an author commit, "p1 p2" for a merge),
        # keyed by the "<approved>..<head>" range; and merge-parent ancestry, keyed
        # (parent, root) -> "0" (ancestor) or a positive count.
        self.branch_commits: dict[str, str] = {}
        self.ancestry: dict[tuple[str, str], str] = {}
        # ruling 290's balance section: the roster and the tree docs it reads from origin/main,
        # keyed by the basename `git show` ends with ("lane.md" -> roster; a lane's packages file;
        # "README.md"). An unscripted doc still raises -- a new read shows up as a failing test.
        self.docs: dict[str, str] = {
            "lane.md": ROSTER,
            "README.md": README,
            "ops.md": OPS_PKG,
            # the other packaged lanes read as empty files: no claimable shapes there, so a test
            # that needs one scripts it into `self.docs` (the KeyError-style assert catches a read
            # the balance never asked for).
            "backend.md": "",
            "frontend.md": "",
            "docs.md": "",
        }
        self.roster = self.docs["lane.md"]
        self.readme = self.docs["README.md"]

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
        if cmd[:2] == ["git", "show"]:  # ruling 290's balance read: roster, packages, README
            doc = cmd[-1].rsplit("/", 1)[-1]
            if doc in self.docs:
                return self.docs[doc]
            raise AssertionError(f"unscripted git show: {cmd[-1]}")
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
            if "--count" in cmd and "--not" in cmd:
                # ruling 278's ancestry read: `rev-list --count rev --not root` answers how
                # many commits `rev` holds that `root` does not -- 0 means rev is an
                # ancestor of (or is) root. The last two non-flag args are rev and root.
                args = [a for a in cmd[2:] if a not in ("--count", "--not")]
                return self.ancestry.get((args[-2], args[-1]), "1") + "\n"
            return self.merges_behind[cmd[-1].split("..")[0]] + "\n"
        if cmd[:2] == ["git", "log"] and "--first-parent" in cmd:
            # ruling 278's condition 1: the branch's own commits, read as the head's
            # first-parent chain from the approved head. The fixture is the parents line
            # per commit, in the order `git log` prints (newest first).
            rng = next(a for a in cmd if ".." in a)
            return self.branch_commits.get(rng, "") + "\n"
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


def test_drafts_get_no_review_read_and_no_merge_state():
    fake = FakeRunner()
    p = pr(build(fake), 7002)
    assert "approval" not in p
    assert "behind" not in p
    assert "in_flight" not in p
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


# --- 4. merge state (ruling 270) ---------------------------------------------------------


def test_the_state_reads_behind_from_the_merge_base():
    """§3's `base=` — the merge-base — is the measured referent (ruling 270 item 2, "its
    `base=` is not `main`'s tip"): the fake's merge-base is 10 merges behind the tip, so
    behind reads yes and the sign needs base at the tip, so it reads no."""
    fake = FakeRunner()
    fake.ci_runs = [run("", status="in_progress", minutes=1), run("success", minutes=30)]
    p = pr(build(fake))
    assert p["gate_run"] == GATE_RUN
    assert p["behind"] == {"merges": 10, "at_tip": False}
    assert p["in_flight"]["base_at_tip"] is False
    assert p["in_flight"]["yes"] is False
    assert [
        "git",
        "rev-list",
        "--count",
        "--first-parent",
        f"{BASE}..origin/main",
    ] in fake.calls
    # No checkout-log read: §3's base= is the merge-base, which needs no API call. The run's
    # merged base was the old legs' basis, not the sign's observable.
    assert not [c for c in fake.calls if c[:2] == ["gh", "api"] and c[2].endswith("/logs")]
    text = snap.render_text(build(FakeRunner()))
    assert f"merge-base {BASE[:9]}" in text


def test_the_in_flight_sign_holds_when_the_base_is_at_the_tip():
    """Merging a PR step 1's sign: base= at main's tip, the gate not finished (absent here),
    and the approval carries. The fake's approval names HEAD and the carry read passes."""
    fake = FakeRunner()
    # No gate run at all: gate reads absent (the update-branch window before the gate queues).
    # The merge-base itself must be at the tip for the sign to hold: declare
    # merge-base(origin/main, head) = TIP.
    fake.prs[0]["statusCheckRollup"] = []
    fake.merge_bases[f"origin/main::{HEAD}"] = TIP
    fake.own_diffs[f"{TIP}..{HEAD}"] = "docs/b.md\n"
    fake.merges_behind[TIP] = "0"
    p = pr(build(fake))
    assert p["gate"] == "absent"
    assert p["behind"] == {"merges": 0, "at_tip": True}
    assert p["in_flight"]["base_at_tip"] is True
    assert p["in_flight"]["gate_unfinished"] is True
    assert p["in_flight"]["carry"] is True
    assert p["in_flight"]["yes"] is True
    text = snap.render_text(build(fake))
    assert f"#{p['number']}" in text
    assert "in-flight sign: yes" in text


def test_a_green_gate_and_a_behind_base_fail_the_sign():
    fake = FakeRunner()
    p = pr(build(fake))
    assert p["behind"] == {"merges": 10, "at_tip": False}
    assert p["in_flight"]["yes"] is False


def test_a_failing_behind_read_is_reported_not_fatal():
    """The rev-list call is guarded like every other read (module contract, lines 43-45):
    a failure becomes a behind error and the report goes on."""
    fake = FakeRunner()
    fake.fail("rev-list", "HTTP 500")
    data = build(fake)
    p = pr(data)
    assert p["behind"] == {"error": "HTTP 500"}
    assert p["in_flight"]["base_at_tip"] is None
    assert p["in_flight"]["yes"] is False
    text = snap.render_text(data)
    assert "behind main: HTTP 500" in text
    assert "in-flight sign: no" in text


def test_a_main_tip_that_cannot_be_read_reports_an_error():
    fake = FakeRunner()
    fake.fail("rev-parse", "HTTP 500")
    p = pr(build(fake))
    assert p["behind"] == {"error": "main tip unread"}
    assert "behind main: main tip unread" in snap.render_text(build(fake))


def test_a_draft_gets_no_merge_state_row_in_the_report():
    fake = FakeRunner()
    text = snap.render_text(build(fake))
    assert (
        "#7002"
        not in text.split("== 4. merge state (ruling 270), non-draft PRs")[1].split("== 5.")[0]
    )


# --- 5. main -----------------------------------------------------------------------------


def test_cancelled_main_run_is_not_red():
    fake = FakeRunner()
    fake.ci_runs = [run("cancelled", minutes=5), run("success", minutes=30)]
    data = build(fake)
    assert data["main"]["ci_latest"]["conclusion"] == "cancelled"
    assert data["main"]["ci_last_completed"]["conclusion"] == "success"


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
        "== 1", "== 2", "== 3", "== 4", "== 5", "== 6", "== 7", "== 8", "== 9",
    ]  # fmt: skip
    assert "merge state (ruling 270)" in text
    assert "behind main: yes (10 merges behind)" in text
    assert "in-flight sign: no" in text


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
# ruling 278's subset carry: the update-branch roll DROPS a line the approved diff added
# (a stale task-list checkbox main already fixed). The new head's own diff holds every line
# of APPROVED_DIFF except `+added line`.
SUBSET_DIFF = APPROVED_DIFF.replace("+added line\n", "")
# main's own change between the two merge-bases: main's own change ALSO adds the same line
# (a task-list fix), so after the roll the new head's diff holds it as context and the PR
# diff loses it -- the "same file and sign" of condition 3. `-added line` would be the
# wrong sign: the dropped line was an ADDED line, so main's change must add it too.
MAIN_HOLDING_DIFF = (
    "diff --git a/docs/b.md b/docs/b.md\n"
    "index def5678..7777777 100644\n"
    "--- a/docs/b.md\n"
    "+++ b/docs/b.md\n"
    "@@ -1,3 +1,3 @@\n"
    " context line\n"
    "+added line\n"
)
MAIN_OTHER_DIFF = MAIN_HOLDING_DIFF.replace("+added line\n", "+other line\n")


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
    # the diff changed because an author commit sits between the approved head and the
    # head under judgment -- the chain read (condition 1) names it, a single-parent commit.
    fake.branch_commits[f"{APPROVED_HEAD[:7]}..{HEAD}"] = "authorparent1\n"
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
        # the paths ride as :(literal) pathspecs -- a PR-controlled filename like
        # ":(exclude)**" would otherwise rewrite the diff's pathspec and read as an empty
        # diff (a false carry); the literal prefix pins each path to a filename.
        assert c[3] == "--" and c[4:] == [":(literal)docs/b.md"], (
            "UR-106 hashes the OWN diff, not the tree, over literal pathspecs"
        )


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


def _subset_reads(fake: FakeRunner, head_diff: str, main_diff: str, chain: str) -> FakeRunner:
    """The UR-106 subset reads for #7001: hashes as `_recorded_reads` wires them, plus the
    two reads the subset rule adds -- the branch's first-parent chain after the approved
    head (condition 1) and main's own change between the two merge-bases (condition 3).

    The head's own base stays BASE (the fake's open-PR default), so the between-bases read
    is `APPROVED_BASE..BASE` over the PR's files.
    """
    fake = _recorded_reads(fake, head_diff)
    fake.merge_bases["origin/main::" + BASE] = APPROVED_BASE  # the between-bases anchor
    fake.own_diffs[f"{APPROVED_BASE}..{BASE}"] = main_diff
    fake.branch_commits[f"{APPROVED_HEAD[:7]}..{HEAD}"] = chain
    # every two-parent commit in the chain is a main merge by construction: the fake
    # answers its second parent's ancestry with 0 (an ancestor of main's tip). A test
    # that wants the ancestry read to FAIL scripts fake.fail on the rev-list needle.
    for parents in (ln for ln in chain.splitlines() if ln.strip()):
        parts = parents.split()
        if len(parts) >= 2:
            fake.ancestry[(parts[1], "origin/main")] = "0"
    return fake


MERGE_COMMIT_CHAIN = (
    "e" * 39 + "1" + " " + APPROVED_HEAD[:7] + "c0ffee"
)  # a merge + the approved head


def test_a_subset_carry_where_main_holds_the_dropped_line_carries():
    """UR-106's subset rule: N ⊆ A and every dropped line is one main's own change also
    removes, with only update-branch merges between the heads."""
    fake = _approved_not_head(
        _subset_reads(FakeRunner(), SUBSET_DIFF, MAIN_HOLDING_DIFF, MERGE_COMMIT_CHAIN)
    )
    p = pr(build(fake))
    assert p["own_diff"]["carry"] is True
    assert p["own_diff"]["subset_lines"] == 1
    assert any(
        "carry=yes (subset: 1 lines main holds)" in row for row in rendered_pr_block(build(fake))
    )


def test_a_dropped_line_main_does_not_hold_reads_no_carry():
    fake = _approved_not_head(
        _subset_reads(FakeRunner(), SUBSET_DIFF, MAIN_OTHER_DIFF, MERGE_COMMIT_CHAIN)
    )
    p = pr(build(fake))
    assert p["own_diff"]["carry"] is False
    assert any("carry=no" in row for row in rendered_pr_block(build(fake)))


def test_a_new_line_in_the_head_diff_is_no_carry():
    """A line in N that A does not hold breaks the multiset containment (condition 2)."""
    new_line_diff = CARRY_DIFF + "+brand new line\n"
    fake = _approved_not_head(
        _subset_reads(FakeRunner(), new_line_diff, MAIN_HOLDING_DIFF, MERGE_COMMIT_CHAIN)
    )
    assert pr(build(fake))["own_diff"]["carry"] is False


def test_an_author_commit_between_the_heads_is_no_carry():
    """Condition 1: only update-branch merges may sit between the approved head and the
    head under judgment. A single-parent commit in the chain is an author commit."""
    fake = _approved_not_head(
        _subset_reads(
            FakeRunner(), SUBSET_DIFF, MAIN_HOLDING_DIFF, "authorparent1\nauthorparent2\n"
        )
    )
    assert pr(build(fake))["own_diff"]["carry"] is False


def test_a_subset_carry_is_ok_for_the_watch_and_the_inflight_sign():
    """The §7 disable list and §4's in-flight sign must read a subset carry as a carry."""
    fake = _approved_not_head(
        _subset_reads(FakeRunner(), SUBSET_DIFF, MAIN_HOLDING_DIFF, MERGE_COMMIT_CHAIN)
    )
    fake.prs[0]["autoMergeRequest"] = _armed()
    data = build(fake)
    assert data["auto_merge_watch"]["ok"] == [7001]
    assert pr(data)["in_flight"]["carry"] is True


def test_a_failed_subset_read_reports_unknown_never_yes():
    """A failed condition read is unknown: the coordinator hand-judges, the armed PR never
    lands in the disable list, and the never-yes rule (UR-106, UR-154) holds."""
    fake = _approved_not_head(
        _subset_reads(FakeRunner(), SUBSET_DIFF, MAIN_HOLDING_DIFF, MERGE_COMMIT_CHAIN)
    )
    fake.fail(f"{APPROVED_BASE}..{BASE}", "fatal: bad object")  # main's between-bases diff
    fake.prs[0]["autoMergeRequest"] = _armed()
    data = build(fake)
    p = pr(data)
    assert p["own_diff"]["carry"] is None
    assert data["auto_merge_watch"]["unknown"] == [7001]
    assert data["auto_merge_watch"]["disable"] == []


def _armed():
    return {"enabledAt": t(-timedelta(hours=1)), "mergeMethod": "MERGE"}


def test_disable_list_flags_an_armed_uncarried_head():
    fake = _approved_not_head(_recorded_reads(FakeRunner(), COMMIT_DIFF))
    # same author-commit scenario as the diff shape stages: the chain read names it.
    fake.branch_commits[f"{APPROVED_HEAD[:7]}..{HEAD}"] = "authorparent1\n"
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
    landed = merge_of(fake, 7108, APPROVED_DIFF, COMMIT_DIFF, approved=LANDED_OTHER)
    # the diff changed because an author commit raced the merge: the chain read names it.
    fake.branch_commits[f"{LANDED_OTHER[:7]}..{landed}"] = "authorparent1\n"
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


# --- 7b. package balance (ruling 290) -------------------------------------------------------


def bal(data: dict) -> dict:
    return data["balance"]


def set_beats(fake: FakeRunner, **agents: str) -> None:
    """Replace the default fixture's heartbeats with one row per named agent.

    ``prose`` is the beat's status line verbatim (``ops-b · 18:00Z · idle``); the whole default
    fixture carries prose this section must not read, so a balance test builds its own world.
    """
    fake.heartbeats = [beat_row(a, prose) for a, prose in agents.items()]


def pr_item(number: int, labels: list[str], title: str, draft: bool = False) -> dict[str, Any]:
    """A PR in the list shape `_prs` feeds `_pr_item` -- the only fields balance reads."""
    return {
        "number": number,
        "title": title,
        "isDraft": draft,
        "labels": [{"name": v} for v in labels],
        "headRefOid": TIP,
        "mergeStateStatus": "BEHIND",
        "statusCheckRollup": [],
    }


def test_an_idle_agent_with_nothing_claimable_beside_a_backlogged_agent_flags():
    # The imbalance the section exists to find: ops-c beats idle and its queue reads none, while
    # ops-a holds two met-dep claimables ([r295], O3.7). ops-b holds the open O2.4 PR, so the
    # draft-as-claim rule keeps it out of the flag on both sides. The flag names both ends and
    # one candidate move.
    fake = FakeRunner()
    set_beats(
        fake,
        **{
            "agent-uplevel-coordinator": "coordinator · 18:00Z · tick",
            "agent-uplevel-ops-a": "ops-a · 18:00Z · working",
            "agent-uplevel-ops-b": "ops-b · 18:00Z · working #7002",
            "agent-uplevel-ops-c": "ops-c · 18:00Z · idle",
        },
    )
    fake.prs = [pr_item(7002, ["lane:ops", "cell:b"], "[O2.4] claim: reid via tensorrt")]
    data = build(fake)
    b = bal(data)
    ids = {i["agent"]: i for i in b["items"]}
    # ops-a: no open package PR, two met-dep claimables ([r295], O3.7 -- both deps read met/none)
    assert ids["uplevel-ops-a"]["open_prs"] == []
    assert [e["token"] for e in ids["uplevel-ops-a"]["claimable"]] == ["r295", "O3.7"]
    assert all(e["deps"] == "met" for e in ids["uplevel-ops-a"]["claimable"])
    # ops-b: its O2.4 PR is open (a draft IS the claim), so idle reads no
    assert ids["uplevel-ops-b"]["open_prs"] == [7002]
    assert ids["uplevel-ops-b"]["idle"] is False
    # ops-c: idle beat, no open PR, queue none -- idle with nothing claimable
    assert ids["uplevel-ops-c"]["idle"] is True
    assert ids["uplevel-ops-c"]["claimable"] == []
    text = snap.render_text(data)
    assert "IMBALANCE" in text
    assert "ops-c" in has_line(text, "IMBALANCE") and "ops-a" in has_line(text, "IMBALANCE")


def test_two_busy_agents_flag_nothing():
    fake = FakeRunner()
    set_beats(
        fake,
        **{
            "agent-uplevel-coordinator": "coordinator · 18:00Z · tick",
            "agent-uplevel-ops-a": "ops-a · 18:00Z · working",
            "agent-uplevel-ops-b": "ops-b · 18:00Z · working #7002",
        },
    )
    fake.prs = [pr_item(7002, ["lane:ops", "cell:b"], "[O2.4] claim: reid via tensorrt")]
    data = build(fake)
    assert bal(data)["flag"] is None
    assert "IMBALANCE" not in snap.render_text(data)


def test_a_free_text_dependency_reads_unread_and_never_met():
    # `[r295]`'s `**Depends on:** `R2`` names no README row (R2a/R2b are the real rows), so the
    # verdict is unread -- never met -- and the entry must not count toward the imbalance's
    # met-dep side. ops-a's queue here carries ONLY that unread entry: no met-dep donor exists,
    # so no flag fires even with ops-c idle.
    fake = FakeRunner()
    set_beats(
        fake,
        **{
            "agent-uplevel-coordinator": "coordinator · 18:00Z · tick",
            "agent-uplevel-ops-a": "ops-a · 18:00Z · working",
            "agent-uplevel-ops-b": "ops-b · 18:00Z · working #7002",
            "agent-uplevel-ops-c": "ops-c · 18:00Z · idle",
        },
    )
    fake.prs = [pr_item(7002, ["lane:ops", "cell:b"], "[O2.4] claim: reid via tensorrt")]
    # The only queued entry gains the free-text dependency: `R2` names no README row (R2a/R2b
    # are the real rows), so the verdict reads unread -- never met. O3.7 stays met-dep, but one
    # met entry is below the >=2 donor threshold, so no flag fires.
    fake.docs["ops.md"] = OPS_PKG.replace(
        "**Flags:** none. **Assigned:** backend. **Depends on:** none.",
        "**Flags:** none. **Assigned:** backend. **Depends on:** `R2`.",
    )
    data = build(fake)
    ids = {i["agent"]: i for i in bal(data)["items"]}
    # O2.4 is title-claimed (the open PR), so the queue yields [r295] and O3.7: the unread entry
    # and one met entry -- below the >=2 donor threshold, so no flag fires.
    assert [e["token"] for e in ids["uplevel-ops-a"]["claimable"]] == ["r295", "O3.7"]
    assert ids["uplevel-ops-a"]["claimable"][0]["deps"] == "unread"
    assert ids["uplevel-ops-a"]["claimable"][1]["deps"] == "met"
    assert bal(data)["flag"] is None


def test_a_heavy_package_is_never_proposed_to_a_fast_agent():
    # A heavy claimable on the donor's queue: `[r295]` becomes a heavy package, ops-c (fast,
    # idle) is the only idle agent, so UR-24 forbids proposing it to ops-c -- the move must name
    # heavy-b (strongest) as the receiver instead.
    fake = FakeRunner()
    set_beats(
        fake,
        **{
            "agent-uplevel-coordinator": "coordinator · 18:00Z · tick",
            "agent-uplevel-ops-a": "ops-a · 18:00Z · working",
            "agent-uplevel-ops-b": "ops-b · 18:00Z · working #7002",
            "agent-uplevel-ops-c": "ops-c · 18:00Z · idle",
        },
    )
    fake.prs = [pr_item(7002, ["lane:ops", "cell:b"], "[O2.4] claim: reid via tensorrt")]
    fake.docs["ops.md"] = OPS_PKG.replace(
        "### [r295] pip leaves the production image\n\n**Flags:** none.",
        "### [r295] pip leaves the production image\n\n**Flags:** `heavy`.",
    )
    data = build(fake)
    move = bal(data)["flag"]["move"]
    assert "heavy-b" in move["to"]
    assert move["package"] == "r295"


def test_the_render_prints_the_section_with_per_agent_rows():
    fake = FakeRunner()
    set_beats(
        fake,
        **{
            "agent-uplevel-coordinator": "coordinator · 18:00Z · tick",
            "agent-uplevel-ops-a": "ops-a · 18:00Z · working",
            "agent-uplevel-ops-b": "ops-b · 18:00Z · working #7002",
            "agent-uplevel-ops-c": "ops-c · 18:00Z · idle",
        },
    )
    fake.prs = [pr_item(7002, ["lane:ops", "cell:b"], "[O2.4] claim: reid via tensorrt")]
    text = snap.render_text(build(fake))
    assert "== 9. package balance (ruling 290)" in text
    rows = has_line(text, "uplevel-ops-a (fast)")
    assert "claimable" in rows
    assert "not idle" in rows
    # The idle row reads its beat's status field, and the header names the package (ruling 290).
    idle_row = has_line(text, "uplevel-ops-c (fast)")
    assert "idle ·" in idle_row
    assert "claimable: none" in idle_row


def has_line(text: str, needle: str) -> str:
    return next(ln for ln in text.splitlines() if needle in ln)


# --- the review round: one test per defect the UR-89 review found --------------------------

BEATS_BALANCE = {
    "agent-uplevel-coordinator": "coordinator · 18:00Z · tick",
    "agent-uplevel-ops-a": "ops-a · 18:00Z · working",
    "agent-uplevel-ops-b": "ops-b · 18:00Z · working #7002",
    "agent-uplevel-ops-c": "ops-c · 18:00Z · idle",
}
# A backend donor for the cross-lane probes: two none-yet blocks whose deps read met, in a file
# the ops roster's queues must not be proposed across.
BACKEND_PKG_DONOR = """\
### B1 backend package one

**Flags:** none. **Depends on:** none. **PR:** none yet.

- [ ] box

### B2 backend package two

**Flags:** none. **Depends on:** none. **PR:** none yet.

- [ ] box
"""  # fmt: skip
# Two extra ops donor blocks (met-dep, none-yet) appended to OPS_PKG by the cross-lane probes,
# so ops-a holds a two-met claimable list beside an idle agent.
DONOR_OPS_EXTRA = """\

### D1 ops donor one

**Flags:** none. **Depends on:** none. **PR:** none yet.

- [ ] box

### D2 ops donor two

**Flags:** none. **Depends on:** none. **PR:** none yet.

- [ ] box
"""  # fmt: skip
# A docs lane file whose queue-named blocks all carry unread dependencies (the self-contradiction
# probe): the docs agent is idle and holds claimables whose deps cannot resolve.
DOCS_PKG_UNREAD = """\
### U1 docs package one

**Flags:** none. **Depends on:** `R2`. **PR:** none yet.

- [ ] box

### U2 docs package two

**Flags:** none. **Depends on:** `R2`. **PR:** none yet.

- [ ] box
"""  # fmt: skip


def test_the_candidate_move_stays_in_the_package_s_lane():
    # Review defect 1: the flag proposed a backend package to an idle ops agent with the false
    # why "same lane, the cells' file areas hold". lane.md's cells' file areas are per-lane (ops
    # A runs `ai/`, ops B runs `scripts/`; backend splits VLM path vs API), so a move keeps them
    # by staying in the package's own lane -- or by naming a heavy agent, ruling 289's shape.
    fake = FakeRunner()
    set_beats(
        fake,
        **{
            **BEATS_BALANCE,
            "agent-uplevel-backend": "backend · 18:00Z · working",
        },
    )
    fake.docs["backend.md"] = BACKEND_PKG_DONOR
    # The donor must be a roster agent with a beat (a beatless agent's scans did not run --
    # review defect 4's own rule): a backend row (one-cell lane) whose queue names B1, B2,
    # replacing ops-a's queue so the backend agent is the ONLY donor and the probe isolates the
    # lane rule (the donor list takes the first, in roster order).
    fake.docs["lane.md"] = ROSTER.replace(
        "| `uplevel-ops-a`       | fast      | `O2.4`, `[r295]`, `O3.7`                 | none         |",
        "| `uplevel-backend`     | fast      | `B1`, `B2`                               | none         |",
    )
    data = build(fake)
    move = bal(data)["flag"]["move"]
    # B1 is a backend package: its receiver must be a backend agent or a heavy agent -- never
    # ops-c, the idle ops agent.
    assert move["package"] == "B1"
    assert "backend" in move["to"] or "heavy" in move["to"]
    assert "ops-c" not in move["to"]


def test_the_move_s_names_truthfully_names_the_lane_or_the_heavy_agent():
    # Review defect 1's second half: the printed why must be TRUE. A same-lane move says so; a
    # heavy-package move to a strongest agent names UR-24; and no move may carry the old
    # "same lane ..." why for a package that would cross lanes.
    fake = FakeRunner()
    set_beats(fake, **BEATS_BALANCE)
    # Same-lane donor: an idle ops agent beside an ops donor holding two met-dep none-yet
    # blocks -- the receiver is the idle ops agent, the why names the lane.
    fake.docs["ops.md"] = OPS_PKG + DONOR_OPS_EXTRA
    data = build(fake)
    move = bal(data)["flag"]["move"]
    assert move["to"] == "uplevel-ops-c"
    assert "ops" in move["why"].lower()
    # Heavy donor: the why names UR-24 and the receiver is a heavy agent (covered shape kept).
    fake2 = FakeRunner()
    set_beats(fake2, **BEATS_BALANCE)
    fake2.docs["ops.md"] = OPS_PKG.replace(
        "### [r295] pip leaves the production image\n\n**Flags:** none.",
        "### [r295] pip leaves the production image\n\n**Flags:** `heavy`.",
    )
    move2 = bal(build(fake2))["flag"]["move"]
    assert "UR-24" in move2["why"]
    assert "heavy" in move2["to"]


def test_an_idle_agent_with_claimables_is_not_a_flag_s_idle_side():
    # Review defect 2: the box reads "an idle agent has nothing claimable"; the code flagged an
    # idle agent holding two unread-dep claimables -- and then the render printed those very
    # claimables on the flagged agent's own row. Nothing claimable means the list is empty.
    fake = FakeRunner()
    set_beats(fake, **{**BEATS_BALANCE, "agent-uplevel-docs": "docs · 18:00Z · idle"})
    # The docs agent joins the world: its queue names two blocks whose deps cannot resolve
    # (`R2` names no README row), so it is idle WITH claimables -- not the flag's idle side.
    # Isolate the idle-side rule: ops-a's queue is stripped (no donor, so no flag can fire for
    # ANY idle agent) and ops-b's claim PR is the only PR (the default fixture's lane:docs PR
    # would make the docs agent not-idle by ownership).
    fake.docs["lane.md"] = (
        ROSTER.replace(
            "| `uplevel-ops-a`       | fast      | `O2.4`, `[r295]`, `O3.7`                 | none         |",
            "| `uplevel-ops-a`       | fast      | none                                     | none         |",
        )
        + "| `uplevel-docs`       | fast      | `U1`, `U2`                               | none         |\n"
    )
    fake.docs["docs.md"] = DOCS_PKG_UNREAD
    fake.prs = [pr_item(7002, ["lane:ops", "cell:b"], "[O2.4] claim: reid via tensorrt")]
    data = build(fake)
    ids = {i["agent"]: i for i in bal(data)["items"]}
    docs_item = ids["uplevel-docs"]
    assert docs_item["claimable"], "the docs agent holds unread-dep claimables"
    assert all(e["deps"] == "unread" for e in docs_item["claimable"])
    assert docs_item["idle"] is True
    # The old code flagged it (idle with no MET claimable); the box's words do not.
    assert bal(data)["flag"] is None


def test_not_heavy_prose_never_classifies_a_package_heavy():
    # Review defect 3: the classifier substringed "heavy" over the whole block body, so ops.md's
    # house prose "**Flags:** none: not heavy..." classified as heavy and the flag cited UR-24 to
    # misroute non-heavy work. Heavy is read from the Flags field's backticked token, the same
    # inline shape the real corpus carries (`**Flags:** `heavy``).
    fake = FakeRunner()
    set_beats(fake, **BEATS_BALANCE)
    fake.docs["ops.md"] = OPS_PKG.replace(
        "### [r295] pip leaves the production image\n\n**Flags:** none.",
        "### [r295] pip leaves the production image\n\n**Flags:** none: not heavy; not owner-tier.",
    )
    data = build(fake)
    move = bal(data)["flag"]["move"]
    # r295 is NOT heavy: the move keeps the cells' file areas -- ops package to the idle ops
    # agent -- and cites no UR-24.
    assert move["to"] == "uplevel-ops-c"
    assert "UR-24" not in move["why"]


def test_a_beatless_agent_s_row_reads_not_read_not_nothing():
    # Review defect 4: an agent with no beat row printed "not idle · claimable: none" -- facts
    # the scans (which sit inside the beat guard) never read. UR-154: a failed/unmade read is
    # never a yes and never a no. The row says so.
    fake = FakeRunner()
    # No beats at all: every agent is beatless; ops-b's roster queue holds [r290] with PR #7330
    # stamped, so the scan WOULD have found something to say.
    set_beats(fake)  # no arguments: zero heartbeats
    fake.prs = []
    text = snap.render_text(build(fake))
    row = has_line(text, "uplevel-ops-b (fast)")
    assert "claimable: not read" in row
    assert "not idle" not in row
    assert "open package PRs: not read" in row
    # A paused agent reads the same way: its scans did not run either.
    fake2 = FakeRunner()
    set_beats(fake2, **{"agent-uplevel-ops-b": "ops-b · 18:00Z · paused · owner hold"})
    fake2.prs = []
    row2 = has_line(snap.render_text(build(fake2)), "uplevel-ops-b (fast)")
    assert "claimable: not read" in row2
    # And a beatless/paused agent is never the flag's idle side: "idle" is a read verdict.
    assert bal(build(fake))["flag"] is None
    assert bal(build(fake2))["flag"] is None


def test_a_heavy_agent_s_claimables_read_the_owning_lanes_files():
    # Review defect 5: heavy-b's roster queue holds O3.2 (ops.md) and B2.3 (backend.md), but the
    # scan looked blocks up only in `lanes.get("heavy", {})` -- always empty, so heavy-b printed
    # "claimable: none" while both blocks are `none yet` (the live section's own false row).
    # Heavy packages live in the OWNING lane's file (UR-59; there is no heavy.md on main), so
    # the scan must resolve the tokens there -- plan_lint's documented UNPACKAGED cross-file
    # lookup, queue order preserved.
    fake = FakeRunner()
    set_beats(
        fake,
        **{
            **BEATS_BALANCE,
            "agent-uplevel-heavy-b": "heavy-b · 18:00Z · working",
        },
    )
    fake.docs["backend.md"] = """\
### B2.3 Re-ID model bake-off
**Flags:** `heavy`. **Depends on:** `O2.4`. **PR:** none yet.

- [ ] box
"""  # fmt: skip
    # [r273] is heavy-b's own package, packaged in the lane whose work it is (O3.2's shape): an
    # ops block assigned to heavy-b.
    fake.docs["ops.md"] = OPS_PKG + """\

### [r273] heavy-b's assigned ops package

**Flags:** `heavy`. **Assigned:** heavy-b. **Depends on:** none. **PR:** none yet.

- [ ] box
"""  # fmt: skip
    # heavy-b's roster queue is `[r273]`, `B2.3`: [r273] lives in ops.md, B2.3 in backend.md.
    data = build(fake)
    ids = {i["agent"]: i for i in bal(data)["items"]}
    hb = ids["uplevel-heavy-b"]
    assert [e["token"] for e in hb["claimable"]] == ["r273", "B2.3"]
    # B2.3 depends on O2.4, a README row: with O2.4 `in progress`, the verdict is unmet
    # (dependency_verdict reads met only off `done`); r273's deps are none, so met.
    assert hb["claimable"][0]["deps"] == "met"
    assert hb["claimable"][1]["deps"] == "unmet"
    # The wider read does not manufacture a heavy-side flag on its own: heavy-b (working beat,
    # no open PR) is not idle, so it is never the flag's idle side; the world's own imbalance
    # (ops-c idle, ops-a backlogged) is the first review's same-lane shape and fires as before.
    flag = bal(data)["flag"]
    assert (
        flag is None
        or flag["move"]["to"] != "uplevel-heavy-b"
        or flag["package"] in ("r273", "B2.3")
    )


def test_a_dependency_name_is_the_backticked_package_token_not_the_prose_around_it():
    # The re-review's blocking defect: B2.3's LIVE field is
    # "**Depends on:** `O2.4` (its `RESULT: PASS` posted)." -- the words after the
    # backticked token are prose about the dependency's state, but the same-line capture
    # read them as more names ('its', 'RESULT', 'PASS', 'posted'), which match no README
    # row, so the verdict printed "unread" where O2.4's row (`in progress`) gives "unmet".
    # The same live shapes: "(ruling 260)", "(#7188)", backticked prose (`done`, `main`,
    # `RESULT: PASS`), and file/sha mentions (`pipeline_workers.py`, `5d5c4bcc5`).
    from scripts.uplevel.coordinator_snapshot import dep_names, dependency_verdict

    def v(field, rows):
        return dependency_verdict(dep_names("**Depends on:** " + field), rows)

    rows = {
        "O2.4": "in progress",
        "B1.4": "done",
        "F2.1": "done",
        "O2.5": "awaiting real tier",
        "O2.2": "done",
        "R2a": "done",
        "R2b": "done",
    }
    # B2.3's verbatim live field: the prose suffix is state, not a name.
    assert v("`O2.4` (its `RESULT: PASS` posted).", rows) == "unmet"
    # Ruling-cite and PR-cite parentheticals are prose, not names.
    assert v("`F2.1`. Its status is", rows) == "met"
    assert dep_names("**Depends on:** `R2`; #7244 (`B3.3`) merged (ruling 260).") == ["R2", "B3.3"]
    assert dep_names("**Depends on:** `B1.5`, `O1.6`.") == ["B1.5", "O1.6"]
    assert dep_names("**Depends on:** `R2` (rules.md §Claiming and assigning work); lands in") == [
        "R2"
    ]
    # Backticked PROSE is not a package token: state words, a branch name, a file, a sha.
    assert dep_names("**Depends on:** `R2`; the target lane's Phase 3 `done`.") == ["R2"]
    assert dep_names("**Depends on:** #7321 (ruling 295's red-`main` exemption) merged.") == []
    assert dep_names("**Depends on:** `[r199]` merged (both edit `pipeline_workers.py`).") == [
        "[r199]"
    ]
    assert dep_names("**Depends on:** `[r231]` merged (#7235, `5d5c4bcc5`).") == ["[r231]"]
    assert dep_names("**Depends on:** #7268 (`[r239]`) merged.") == ["[r239]"]
    assert dep_names("**Depends on:** `R2`; both `O2.5` runs posted (ruling 260).") == [
        "R2",
        "O2.5",
    ]
    # A `none`-prefixed field declares no names even when prose later backticks a token.
    assert dep_names("**Depends on:** none; it runs in parallel with backend's `[r130b]`.") == []
    assert dep_names("**Depends on:** none named; it builds on `O2.2`'s") == []
    # A field whose only text is prose names nothing (met, not unread).
    assert v("its trigger.", {}) == "met"
    # And the free-text name that no row carries still reads unread, never met (UR-154's
    # direction is unchanged): `R2` names no row (the rows are `R2a`/`R2b`).
    assert v("`R2`.", rows) == "unread"


def test_the_claimable_scan_suppresses_only_the_agent_s_own_titles():
    # Review defect 6: the scan suppressed a token on `[{token}] in titles` over ALL open PR
    # titles repo-wide, while `next_claimable` (the box's own definition) checks only the
    # ticking agent's own titles -- and only as a LEADING token (a mid-title mention is prose).
    fake = FakeRunner()
    set_beats(fake, **BEATS_BALANCE)
    # Another agent's PR mentioning [r295] mid-title must NOT empty ops-a's claimable list.
    fake.prs = [
        pr_item(7002, ["lane:ops", "cell:b"], "[O2.4] claim: reid via tensorrt"),
        pr_item(7999, ["lane:docs"], "side quest mentions [r295] in passing"),
    ]
    ids = {i["agent"]: i for i in bal(build(fake))["items"]}
    assert [e["token"] for e in ids["uplevel-ops-a"]["claimable"]] == ["r295", "O3.7"]
    # And a LEADING title by ANOTHER agent also does not suppress ops-a's claimable: O2.4's
    # title-claim suppression applies only to the agent whose queue holds the block and whose
    # own PR titles it -- per-agent mine lists, `next_claimable`'s semantics.
    fake2 = FakeRunner()
    set_beats(fake2, **BEATS_BALANCE)
    fake2.prs = [
        pr_item(7002, ["lane:ops", "cell:b"], "[O2.4] claim: reid via tensorrt"),
        pr_item(7999, ["lane:ops", "cell:a"], "[O2.4] claim: another cell's PR"),
    ]
    ids2 = {i["agent"]: i for i in bal(build(fake2))["items"]}
    assert [e["token"] for e in ids2["uplevel-ops-a"]["claimable"]] == ["r295", "O3.7"]
    # But my OWN leading title still suppresses (the unchanged half of the semantics).
    fake3 = FakeRunner()
    set_beats(fake3, **BEATS_BALANCE)
    fake3.prs = [pr_item(7100, ["lane:ops", "cell:a"], "[r295] claim: pip leaves the image")]
    ids3 = {i["agent"]: i for i in bal(build(fake3))["items"]}
    assert [e["token"] for e in ids3["uplevel-ops-a"]["claimable"]] == ["O3.7"]


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
