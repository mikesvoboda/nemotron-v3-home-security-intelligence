#!/usr/bin/env python3
"""Tests for scripts/uplevel/plan_lint.py (ruling 197): one per failure kind, plus the real tree.

Run explicitly; outside testpaths (like every scripts/test_*.py gate suite):

    uv run python -m pytest scripts/test_plan_lint.py -q

Each failure kind is planted in a small tree in ``tmp_path`` that is clean before the plant, so a
test fails for its own finding and not for some other line of the fixture. The last test runs the
lint over this checkout's own plan files: the fixtures prove the checks can fire, the real tree
proves the plan the lanes act on passes them.
"""

from __future__ import annotations

import importlib.util
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


snap = _load("coordinator_snapshot", UPLEVEL / "coordinator_snapshot.py")
tick = _load("lane_tick", UPLEVEL / "lane_tick.py")
lint = _load("plan_lint", UPLEVEL / "plan_lint.py")

# roles/lane.md's roster shape, shortened: `F2.3` on several queues (the shared package), a `none`
# label row whose queue names packages no file here carries (skipped, as the digest skips it).
ROSTER = """\
## Who takes what

| sandbox               | model     | queue                                              | review label      |
| --------------------- | --------- | -------------------------------------------------- | ----------------- |
| `uplevel-coordinator` | fast      | routing (`roles/coordinator.md`)                   | none              |
| `uplevel-backend`     | fast      | `[r129]`, `F2.3` API batches                       | `review:backend`  |
| `uplevel-frontend`    | fast      | `[r132]`, `F2.3` UI (FE-1)                         | `review:frontend` |
| `uplevel-ops-a`       | fast      | `[r189]`, `F2.3` UI (OP-2), `O2.5`                 | `review:ops-a`    |
| `uplevel-ops-b`       | fast      | `[r157]`, `[r172]`                                 | `review:ops-b`    |
| `uplevel-docs`        | fast      | `[r165b]`                                          | `review:docs`     |
| `uplevel-heavy-a`     | strongest | then `heavy` PRs: `B3.2`, `[r999]`                 | none              |
| `uplevel-operator`    | fast      | `O2.5`, `[r999]`                                   | none              |
"""
BACKEND = """\
# Backend

### [r129] A backend fix

**Flags:** none. **Assigned:** `uplevel-backend`. **PR:** #7001 (open).

- [ ] box
"""
FRONTEND = """\
# Frontend

### F2.3 Golden paths for every working feature

**Flags:** none. **Depends on:** `F2.1`.

### [r132] F-022: retire the rate-limit countdown

**Flags:** none. **Assigned:** `uplevel-frontend`.
**PR:** none yet.
"""
OPS = """\
# Ops

### O2.5 Production-shape real tier

**Flags:** none: not heavy.

### [r157] O2.4 independent plan builds

**Flags:** none. **Assigned:** `uplevel-ops-b`. **PR:** #7087. (rulings 157)

### [r189] The golden leg's cap

**Flags:** none. **Assigned:** `uplevel-ops-a`. **PR:** none yet. (ruling 189)

### [r172] A per-module import budget

**Flags:** none. **Assigned:** `uplevel-ops-b`, after `[r157]`. **PR:**
none yet. (ruling 172; issue #7102)
"""
DOCS = """\
# Docs

### [r165b] F-007: cure a quarantined spec

**Flags:** none. **PR:** none yet.
"""
MAP = """\
# Ruling map

## Rulings

| ruling | became |
| ------ | ------ |
| 1      | UR-33 (carried by a PR; no record id) |
| 176    | UR-180 (no id: before the record filter) |
| 177    | lane.md step 1 (record 6172198207) |
| 178    | lane.md beat (6172424097) |

## Owner records

| record     | became |
| ---------- | ------ |
| 6074248201 | UR-52  |
"""


def tree(tmp_path: Path, **over: str) -> Path:
    files = {
        "docs/uplevel/roles/lane.md": over.get("roster", ROSTER),
        "docs/uplevel/packages/backend.md": over.get("backend", BACKEND),
        "docs/uplevel/packages/frontend.md": over.get("frontend", FRONTEND),
        "docs/uplevel/packages/ops.md": over.get("ops", OPS),
        "docs/uplevel/packages/docs.md": over.get("docs", DOCS),
        "docs/uplevel/history/ruling-map.md": over.get("map", MAP),
    }
    for rel, text in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    return tmp_path


def findings(tmp_path: Path, **over: str) -> list[str]:
    return lint.lint(tree(tmp_path, **over))[0]


# --- the parsers are lane_tick's ------------------------------------------------------------


def test_the_lint_reads_with_lane_ticks_own_parser_objects():
    # Imported, never re-implemented: a copy could pass a field the digest then misreads.
    shared = ("ROW", "queue_entries", "QUEUE_TOKEN", "BLOCK", "PKG_FIELD", "NONE_YET", "PR_NUMBER",
              "next_claimable", "held_claims")  # fmt: skip
    for name in shared:
        assert getattr(lint, name) is getattr(tick, name), name
    assert set(lint.PARSERS) == {getattr(tick, n) for n in shared}
    # and the same files the digest reads from origin/main, here from the tree under review
    assert tick.ROSTER.split(":", 1)[1] == lint.ROSTER_PATH
    assert tick.MAP.split(":", 1)[1] == lint.MAP_PATH


@pytest.fixture
def clean(tmp_path):
    """The unplanted fixture tree, asserted clean: the control each planted defect is measured on."""
    assert findings(tmp_path) == []
    return tmp_path


def test_the_fixture_tree_is_clean_before_any_plant(clean):
    assert clean


# --- 1. a roster token with no block in its lane's file --------------------------------------


def test_a_queue_token_with_no_block_in_its_lanes_file_is_named_with_its_roster_line(tmp_path):
    roster = ROSTER.replace("`[r157]`, `[r172]`", "`[r157]`, `[r184]`, `[r172]`")
    got = findings(tmp_path, roster=roster)
    assert got == [
        "docs/uplevel/roles/lane.md:9: ops-b queue token r184 has no package block in "
        "docs/uplevel/packages/ops.md"
    ]
    # the digest's own behaviour on that slot, which is why it is a finding: skipped, silently
    assert tick.next_claimable(OPS, ["r184"], []) is None


def test_a_block_in_another_lanes_file_does_not_satisfy_the_check(tmp_path):
    # lane_tick reads ONLY my lane's file, so ops-b's [r132] (a frontend block) is never offered.
    got = findings(tmp_path, roster=ROSTER.replace("`[r157]`, `[r172]`", "`[r157]`, `[r132]`, `[r172]`"))  # fmt: skip
    assert any("ops-b queue token r132 has no package block in docs/uplevel/packages/ops.md" in f for f in got), got  # fmt: skip


def test_a_none_label_row_is_skipped(clean):
    # heavy-a's and the operator's `[r999]` have no block anywhere and the tree is still clean.
    assert "[r999]" in ROSTER


def test_the_shared_package_is_held_to_its_home_file(tmp_path):
    # F2.3 sits on four queues in the fixture and is clean; delete its frontend block and every
    # queue that carries it is a finding -- the exemption cannot hide a vanished block.
    frontend = FRONTEND.replace("### F2.3 Golden paths for every working feature\n", "")
    got = findings(tmp_path, frontend=frontend)
    assert len(got) == 3, got
    assert all("F2.3 is shared" in f and "frontend.md has no block" in f for f in got), got


# --- 2. a **PR:** field lane_tick reads as neither state ------------------------------------


def test_a_none_yet_wrapped_across_two_lines_is_a_finding(tmp_path):
    # [r196a]'s first draft: `**PR:** none` / `yet.` -- NONE_YET cannot span the newline.
    docs = DOCS.replace("**PR:** none yet.", "**PR:** none\nyet.")
    got = findings(tmp_path, docs=docs)
    assert len(got) == 1, got
    assert got[0].startswith("docs/uplevel/packages/docs.md:5: [r165b] **PR:** reads 'none yet.'")
    # ...the digest's reading of it, which is the defect: neither offered nor held
    assert tick.next_claimable(docs, ["r165b"], []) is None
    assert tick.held_claims(docs, []) == []


@pytest.mark.parametrize(
    "value",
    ["none.", "TBD", "pending (ruling 165)", "`none`", "n/a"],
)
def test_a_pr_field_with_neither_none_yet_nor_a_number_is_a_finding(tmp_path, value):
    got = findings(tmp_path, docs=DOCS.replace("none yet.", value))
    assert len(got) == 1 and "[r165b] **PR:**" in got[0], got


@pytest.mark.parametrize(
    "value",
    [
        "none yet.",
        "\nnone yet. (ruling 172)",  # the header wrap: the whole value on the next line is fine
        "#7200 (open)",
        "none yet. (ruling 172; issue #7102)",
        "#7114 (merged), follow-up none yet",
    ],
)
def test_the_fields_lane_tick_reads_are_clean(tmp_path, value):
    assert findings(tmp_path, docs=DOCS.replace(" none yet.", " " + value)) == []


def test_a_block_with_no_pr_field_is_not_this_checks_business(clean):
    # Plan packages (O2.5, F2.3 here) carry no `**PR:**` field; lane_tick never offers them either.
    assert "O2.5" in OPS and "**PR:**" not in OPS.split("### ")[1]


# --- 3. one token on two lanes' queues -----------------------------------------------------


def test_a_token_on_two_lanes_queues_is_a_finding(tmp_path):
    roster = ROSTER.replace("`[r165b]`", "`[r165b]`, `[r157]`")
    got = findings(tmp_path, roster=roster)
    assert "docs/uplevel/roles/lane.md:10: token r157 is on two lanes' queues: ops-b (line 9) and docs" in got  # fmt: skip


def test_two_cells_of_one_lane_are_two_queues(tmp_path):
    # ops-a and ops-b claim from their own rows (UR-52): one token on both is offered to both.
    roster = ROSTER.replace("`[r189]`, ", "`[r189]`, `[r157]`, ")
    got = findings(tmp_path, roster=roster)
    assert any("token r157 is on two lanes' queues: ops-a (line 8) and ops-b" in f for f in got), got  # fmt: skip


def test_a_none_label_rows_queue_is_not_counted_against_a_lanes(clean):
    # O2.5 is on ops-a's queue and the operator's (the operator RUNS it, ruling 188): not a finding.
    assert ROSTER.count("`O2.5`") == 2


# --- 4. a ruling-map row without its record id ---------------------------------------------


def test_a_ruling_row_from_177_on_without_a_record_id_is_a_finding(tmp_path):
    rows = MAP.replace("| 178    | lane.md beat (6172424097) |", "| 178    | lane.md beat |")
    got = findings(tmp_path, map=rows)
    assert got == ["docs/uplevel/history/ruling-map.md:10: ruling 178's row names no record id"]


def test_rows_before_177_and_owner_record_rows_are_not_checked(clean):
    # 1 and 176 carry no id in the fixture (as rows 1-145 and 147 do on main); owner-record rows
    # are a different table, keyed by the id itself.
    assert "| 176    | UR-180 (no id" in MAP


def test_a_nine_or_eleven_digit_number_is_not_a_record_id(tmp_path):
    for digits in ("617242409", "61724240971"):
        rows = MAP.replace("6172424097", digits)
        assert findings(tmp_path, map=rows) == ["docs/uplevel/history/ruling-map.md:10: ruling 178's row names no record id"]  # fmt: skip


# --- an empty read is never clean ----------------------------------------------------------


@pytest.mark.parametrize(
    ("over", "needle"),
    [
        ({"roster": "no table here\n"}, "no roster row read"),
        ({"map": MAP.replace("## Rulings", "## Something else")}, "no row read under '## Rulings'"),
    ],
)
def test_a_read_that_finds_nothing_is_a_finding_not_a_pass(tmp_path, over, needle):
    assert any(needle in f for f in findings(tmp_path, **over))


def test_a_missing_package_file_is_a_finding(tmp_path):
    root = tree(tmp_path)
    (root / "docs/uplevel/packages/docs.md").unlink()
    got, _ = lint.lint(root)
    assert any(f.startswith("docs/uplevel/packages/docs.md:1: unreadable") for f in got), got


# --- the CLI --------------------------------------------------------------------------------


def test_main_exits_0_on_a_clean_tree_and_says_what_it_read(tmp_path, capsys):
    assert lint.main(["--root", str(tree(tmp_path))]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out == ["plan_lint: 0 finding(s); read 8 roster rows, 4 package files (8 blocks), 4 ruling-map rows"]  # fmt: skip


def test_main_exits_1_with_one_file_line_per_finding(tmp_path, capsys):
    root = tree(tmp_path, docs=DOCS.replace("**PR:** none yet.", "**PR:** none\nyet."))
    assert lint.main(["--root", str(root)]) == 1
    out = capsys.readouterr().out.splitlines()
    assert len(out) == 2 and out[0].startswith("docs/uplevel/packages/docs.md:5: ")
    assert out[1].startswith("plan_lint: 1 finding(s);")


# --- the real tree --------------------------------------------------------------------------


def test_the_real_tree_is_clean():
    got, read = lint.lint(REPO_ROOT)
    assert got == [], "\n".join([*got, read])
