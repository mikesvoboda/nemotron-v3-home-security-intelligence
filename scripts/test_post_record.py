#!/usr/bin/env python3
"""Tests for scripts/uplevel/post_record.py (ruling 197), with no network.

Run explicitly; outside testpaths (like every scripts/test_*.py gate suite):

    uv run python -m pytest scripts/test_post_record.py -q

One seam: ``post_record.main(argv, run)`` takes a ``run(cmd, stdin)``; the fake records every call
and answers like ``gh api`` does. The last tests feed what this tool writes into ``lane_tick``'s
reader and its whole digest, so the writer and the reader are pinned against each other, not each
against a fixture of its own.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
UPLEVEL = REPO_ROOT / "scripts" / "uplevel"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# The tool imports its siblings by bare name; register them under those names first.
snap = _load("coordinator_snapshot", UPLEVEL / "coordinator_snapshot.py")
tick = _load("lane_tick", UPLEVEL / "lane_tick.py")
post = _load("post_record", UPLEVEL / "post_record.py")

RECORD = (
    "BINDING NOW · ruling 197: the digest's formats are checked where they are written\n\n"
    "Owner record, 2026-10-15T17:27Z. Binds now.\n"
)
POINTER = "Pointer: the `for you:` line is the one to act on first (ruling 196).\n"


class Fake:
    def __init__(self, answer=None, fail=None):
        self.calls: list[tuple[list[str], str]] = []
        self.answer = (
            answer if answer is not None else {"id": 6199000001, "html_url": "https://x/1"}
        )
        self.fail = fail

    def __call__(self, cmd, stdin):
        self.calls.append(([str(c) for c in cmd], stdin))
        if self.fail:
            raise snap.CommandError(self.fail)
        return json.dumps(self.answer)


def run(tmp_path, args, body, fake=None):
    f = tmp_path / "body.md"
    f.write_text(body, encoding="utf-8")
    fake = fake or Fake()
    code = post.main([*args, "--body-file", str(f), "--repo", "o/r"], run=fake)
    return code, fake


def record_args(ruling="197", lanes="heavy-a,ops-b", packages="r197"):
    return ["record", "--ruling", ruling, "--lanes", lanes, "--packages", packages]


def pointer_args(ruling="196", lane="frontend", pr="7174"):
    return ["pointer", "--ruling", ruling, "--lane", lane, "--pr", pr]


# --- what it posts --------------------------------------------------------------------------


def test_a_record_posts_to_the_owner_issue_through_stdin_with_its_exact_footer(tmp_path, capsys):
    code, fake = run(tmp_path, record_args(), RECORD)
    assert code == 0
    ((cmd, stdin),) = fake.calls
    # stdin, not argv: a multi-line body needs no shell quoting, and `-F body=@-` reads it whole.
    assert cmd == ["gh", "api", "repos/o/r/issues/6854/comments", "-F", "body=@-"]
    assert stdin == RECORD.rstrip() + "\n\n<!-- uplevel: ruling=197 lanes=heavy-a,ops-b packages=r197 -->"  # fmt: skip
    assert "comment 6199000001" in capsys.readouterr().out


def test_a_pointer_posts_to_its_pr_with_the_pointer_footer(tmp_path):
    code, fake = run(tmp_path, pointer_args(), POINTER)
    assert code == 0
    ((cmd, stdin),) = fake.calls
    assert cmd[2] == "repos/o/r/issues/7174/comments"
    assert stdin.endswith("\n\n<!-- uplevel: pointer ruling=196 lane=frontend -->")
    assert (
        stdin.splitlines()[-1] == "<!-- uplevel: pointer ruling=196 lane=frontend -->"
    )  # ONE line


def test_all_and_none_are_written_as_the_bare_words(tmp_path):
    _, fake = run(tmp_path, record_args(lanes="all", packages="none"), RECORD)
    assert fake.calls[0][1].endswith("<!-- uplevel: ruling=197 lanes=all packages=none -->")


def test_dry_run_prints_the_final_body_and_calls_nothing(tmp_path, capsys):
    code, fake = run(tmp_path, [*record_args(), "--dry-run"], RECORD)
    assert code == 0 and fake.calls == []
    printed = capsys.readouterr().out
    assert printed.rstrip("\n").endswith("<!-- uplevel: ruling=197 lanes=heavy-a,ops-b packages=r197 -->")  # fmt: skip
    assert printed.startswith("BINDING NOW · ruling 197")


def test_a_failed_post_exits_1_and_says_so(tmp_path, capsys):
    code, _ = run(tmp_path, record_args(), RECORD, Fake(fail="gh api exited 1: HTTP 502"))
    assert code == 1 and "ERROR post" in capsys.readouterr().err


# --- what it refuses (exit 2, nothing posted) ----------------------------------------------


@pytest.mark.parametrize(
    ("args", "body", "why"),
    [
        # the record's first line is what the snapshot's window and ruling 177's filter key on
        (record_args(), "Owner record: no headline\n", "first line"),
        (record_args(), "**BINDING NOW · ruling 197**: decorated\n", "first line"),
        (record_args(), "BINDING NOW · ruling 196: another ruling's record\n", "first line"),
        # `--ruling 19` on ruling 197's body is a prefix match, not the same ruling
        (record_args(ruling="19"), RECORD, "first line"),
        (record_args(lanes="heavy"), RECORD, "unknown name"),
        (record_args(lanes="agent-uplevel-ops-b"), RECORD, "unknown name"),
        (record_args(lanes="all,ops-b"), RECORD, "unknown name"),
        (record_args(lanes="ops-b,ops-b"), RECORD, "repeated"),
        (record_args(packages="[r197]"), RECORD, "package token"),
        (record_args(packages="r197,none"), RECORD, "package token"),
        (
            record_args(),
            RECORD + "\n<!-- uplevel: ruling=197 lanes=all packages=none -->\n",
            "already carries",
        ),
        (record_args(), "", "empty"),
        (pointer_args(lane="all"), POINTER, "unknown name"),
        (pointer_args(lane="frontend,docs"), POINTER, "one lane"),
        (pointer_args(lane="fe"), POINTER, "unknown name"),
        (
            pointer_args(),
            POINTER + "<!--uplevel: pointer ruling=1 lane=docs -->",
            "already carries",
        ),
    ],
)
def test_a_body_or_name_the_digest_could_not_use_is_refused(tmp_path, capsys, args, body, why):
    code, fake = run(tmp_path, args, body)
    assert code == 2, why
    assert fake.calls == []
    assert why in capsys.readouterr().err


def test_a_missing_body_file_is_refused_not_posted(tmp_path, capsys):
    fake = Fake()
    code = post.main([*record_args(), "--body-file", str(tmp_path / "nope.md")], run=fake)
    assert code == 2 and fake.calls == [] and "body-file" in capsys.readouterr().err


# --- the writer against the reader ----------------------------------------------------------


def test_the_footer_names_are_the_rosters_sandboxes():
    # The names are sandbox names without `agent-`/`uplevel-`. Read from roles/lane.md's own rows
    # with lane_tick's ROW and the snapshot's agent_key, so a new sandbox on the roster fails here
    # until NAMES learns it -- instead of post_record refusing the owner's first record to it.
    roster = (REPO_ROOT / "docs" / "uplevel" / "roles" / "lane.md").read_text(encoding="utf-8")
    rows = [m.group(1) for line in roster.splitlines() if (m := tick.ROW.search(line))]
    assert rows, "no roster rows read"
    assert sorted(tick.footer_name(r) for r in rows) == sorted(tick.NAMES)


@pytest.mark.parametrize(
    "sandbox",
    [
        "agent-uplevel-ops-b",
        "uplevel-ops-b",
        "agent-uplevel-operator",
        "uplevel-heavy-a",
        "agent-uplevel-coordinator",
    ],
)
def test_footer_name_strips_both_live_prefix_spellings(sandbox):
    assert tick.footer_name(sandbox) in tick.NAMES
    assert tick.footer_name(sandbox) == sandbox.removeprefix("agent-").removeprefix("uplevel-")


def test_what_it_writes_is_what_lane_ticks_reader_reads(tmp_path, capsys):
    run(tmp_path, [*record_args(), "--dry-run"], RECORD)
    assert tick.footer(capsys.readouterr().out) == {
        "kind": "record",
        "ruling": 197,
        "lanes": ["heavy-a", "ops-b"],
        "packages": ["r197"],
    }
    run(tmp_path, [*pointer_args(), "--dry-run"], POINTER)
    assert tick.footer(capsys.readouterr().out) == {"kind": "pointer", "ruling": 196, "lane": "frontend"}  # fmt: skip
    # The whole-digest half of this pin -- a posted body served back as a live #6854 comment prints
    # `for you:` for the lanes it names and no other -- lives in test_lane_tick.py, beside the fake
    # that scenario needs (test_a_record_post_record_wrote_reaches_the_lanes_it_names_only).
