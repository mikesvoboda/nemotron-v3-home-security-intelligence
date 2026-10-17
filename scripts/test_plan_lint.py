#!/usr/bin/env python3
"""Tests for scripts/uplevel/plan_lint.py (ruling 197): one per failure kind, and the baseline.

Run explicitly; outside testpaths (like every scripts/test_*.py gate suite):

    uv run python -m pytest scripts/test_plan_lint.py -q

Each failure kind is planted in a small tree in ``tmp_path`` that is clean before the plant, so a
test fails for its own finding and not for some other line of the fixture. Nothing here asserts
that this checkout's own plan files are CLEAN: this suite runs in collection-sanity on every PR, and
a plan defect already on ``main`` would red every one of them. The real tree's cleanliness is the
job of the CI step that runs the lint with the PR merge commit's first parent as ``--baseline``; the
baseline logic it relies on, and the step's own first-parent line, are pinned here on fixtures and
throwaway git repositories. The real roster's SHAPE is used here (ruling 242): copies of this
checkout's roster and package files, with a defect planted, must have that defect caught -- whatever
else the copies hold.
"""

from __future__ import annotations

import importlib.util
import subprocess
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

# roles/lane.md's roster shape, shortened: `F2.3` on several queues (the shared package), every
# review label `none` as ruling 198 left the real roster, a heavy-a row whose tokens live in two
# other lanes' files (it has none of its own), and the operator running ops-a's `O2.5`.
ROSTER = """\
## Who takes what

| sandbox               | model     | queue                                              | review label      |
| --------------------- | --------- | -------------------------------------------------- | ----------------- |
| `uplevel-coordinator` | fast      | routing (`roles/coordinator.md`)                   | none              |
| `uplevel-backend`     | fast      | `[r129]`, `F2.3` API batches                       | none              |
| `uplevel-frontend`    | fast      | `[r132]`, `F2.3` UI (FE-1)                         | none              |
| `uplevel-ops-a`       | fast      | `[r189]`, `F2.3` UI (OP-2), `O2.5`                 | none              |
| `uplevel-ops-b`       | fast      | `[r157]`, `[r172]`                                 | none              |
| `uplevel-docs`        | fast      | `[r165b]`                                          | none              |
| `uplevel-heavy-a`     | strongest | `B3.2`, `O3.6`                                     | none              |
| `uplevel-operator`    | fast      | real-tier runs: `F2.3`'s batches, `O2.5`           | none              |
"""
BACKEND = """\
# Backend

### [r129] A backend fix

**Flags:** none. **Assigned:** `uplevel-backend`. **PR:** #7001 (open).

- [ ] box

### B3.2 Delete the approved module list

**Flags:** `heavy · owner`. **PR:** none yet.
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

### O3.6 PR mutation evidence tool

**Flags:** `heavy`. **PR:** none yet.
"""
DOCS = """\
# Docs

### [r165b] F-007: cure a quarantined spec

**Flags:** none. **PR:** none yet.
"""
# Rows 1 and 147 carry no record id, as on main; every other ruling row must (146, 148 on).
MAP = """\
# Ruling map

## Rulings

| ruling | became |
| ------ | ------ |
| 1      | UR-33 (carried by a PR; no record id) |
| 146    | UR-39 (record 6128714278) |
| 147    | the plan rewrite (owner design session 2026-10-12) |
| 150    | packages (record 6147963319) |
| 176    | UR-180 (record 6172107453) |
| 177    | lane.md step 1 (record 6172198207) |
| 178    | lane.md beat (6172424097) |

## Owner records

| record     | became |
| ---------- | ------ |
| 6074248201 | UR-52  |
"""
FILES = {
    "docs/uplevel/roles/lane.md": ROSTER,
    "docs/uplevel/packages/backend.md": BACKEND,
    "docs/uplevel/packages/frontend.md": FRONTEND,
    "docs/uplevel/packages/ops.md": OPS,
    "docs/uplevel/packages/docs.md": DOCS,
    "docs/uplevel/history/ruling-map.md": MAP,
}
KEYS = {
    "roster": "docs/uplevel/roles/lane.md",
    "backend": "docs/uplevel/packages/backend.md",
    "frontend": "docs/uplevel/packages/frontend.md",
    "ops": "docs/uplevel/packages/ops.md",
    "docs": "docs/uplevel/packages/docs.md",
    "map": "docs/uplevel/history/ruling-map.md",
}


def files(**over: str) -> dict[str, str]:
    return {**FILES, **{KEYS[k]: v for k, v in over.items()}}


def tree(tmp_path: Path, **over: str) -> Path:
    for rel, text in files(**over).items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    return tmp_path


def findings(tmp_path: Path, **over: str) -> list[str]:
    return [str(f) for f in lint.lint(lint.Disk(tree(tmp_path, **over)))[0]]


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


def test_every_row_is_checked_whatever_its_label(tmp_path):
    # Ruling 242: a `none` label used to skip the row, and ruling 198 set every label to `none`, so
    # checks 1 and 3 checked nothing. The fixture's labels are all `none`, as the real roster's are.
    assert "review:" not in ROSTER
    got = findings(tmp_path, roster=ROSTER.replace("`[r165b]`", "`[r165b]`, `[r999]`"))
    assert got == ["docs/uplevel/roles/lane.md:10: docs queue token r999 has no package block in docs/uplevel/packages/docs.md"], got  # fmt: skip


def test_a_row_with_no_package_file_finds_its_tokens_in_any_lanes_file(clean, tmp_path):
    # heavy-a has no heavy.md: its B3.2 (backend.md) and O3.6 (ops.md) are assigned by the
    # coordinator (UR-59) from blocks in other lanes' files, and the clean tree finds both.
    assert not (clean / "docs/uplevel/packages/heavy.md").exists() and "heavy" in lint.UNPACKAGED
    roster = ROSTER.replace("`B3.2`, `O3.6`", "`B3.2`, `O3.6`, `[r999]`")
    got = findings(tmp_path / "planted", roster=roster)
    assert got == ["docs/uplevel/roles/lane.md:11: heavy-a queue token r999 has no package block in docs/uplevel/packages/*.md"], got  # fmt: skip


def test_a_token_on_heavy_as_queue_and_a_lanes_is_a_finding(tmp_path):
    # Ruling 226 split [r196a] between frontend and heavy-a, and both rows led with its token: the
    # digest would offer it to frontend while the coordinator assigns it to heavy-a.
    roster = ROSTER.replace("`B3.2`, `O3.6`", "`B3.2`, `[r132]`, `O3.6`")
    got = findings(tmp_path, roster=roster)
    assert "docs/uplevel/roles/lane.md:11: token r132 is on two lanes' queues: frontend and heavy-a" in got, got  # fmt: skip


def test_a_token_named_inside_an_entrys_prose_is_not_a_slot(clean, tmp_path):
    # The fix for that split on the real roster: "F-012 then F-064 of `[r196a]`" leads with no
    # token, so queue_entries reads no slot, and nothing is offered or doubled.
    roster = ROSTER.replace("`B3.2`, `O3.6`", "`B3.2`, F-012 then F-064 of `[r132]` (ruling 226), `O3.6`")  # fmt: skip
    assert findings(tmp_path / "planted", roster=roster) == []


def test_the_shared_package_is_held_to_its_home_file(tmp_path):
    # F2.3 sits on three lane queues in the fixture and is clean; delete its frontend block and
    # every queue that carries it is a finding -- the exemption cannot hide a vanished block.
    frontend = FRONTEND.replace("### F2.3 Golden paths for every working feature\n", "")
    got = findings(tmp_path, frontend=frontend)
    assert len(got) == 3, got
    assert all("F2.3 is shared" in f and "frontend.md has no block" in f for f in got), got


# --- 2. a **PR:** field lane_tick does not read as offered or held --------------------------


def test_a_none_yet_wrapped_across_two_lines_is_a_finding(tmp_path):
    # [r196a]'s first draft: `**PR:** none` / `yet.` -- NONE_YET cannot span the newline.
    docs = DOCS.replace("**PR:** none yet.", "**PR:** none\nyet.")
    got = findings(tmp_path, docs=docs)
    assert len(got) == 1, got
    assert got[0].startswith("docs/uplevel/packages/docs.md:5: [r165b] **PR:** reads 'none yet.'")
    # ...the digest's reading of it, which is the defect: neither offered nor held
    assert tick.next_claimable(docs, ["r165b"], []) is None
    assert tick.held_claims(docs, []) == []


def test_a_wrapped_none_yet_citing_an_issue_is_a_finding_not_a_hold(tmp_path):
    # The same wrap with `[r172]`'s real tail: held_claims reads the first #N anywhere, so #7102 --
    # an issue -- made the field look held, and the old lint passed it. A hold LEADS with #N.
    ops = OPS.replace("**PR:**\nnone yet. (ruling 172; issue #7102)", "**PR:** none\nyet. (ruling 172; issue #7102)")  # fmt: skip
    got = findings(tmp_path, ops=ops)
    assert len(got) == 1 and "[r172] **PR:** reads 'none yet. (ruling 172; issue #7102)'" in got[0], got  # fmt: skip
    # the digest's own two readings of it: not offered, and "held" by an issue number
    assert tick.next_claimable(ops, ["r172"], []) is None
    assert tick.held_claims(ops, [{"number": 7102, "title": ""}]) == ["r172"]


@pytest.mark.parametrize(
    "value",
    [
        "none.",
        "TBD",
        "pending (ruling 165)",
        "`none`",
        "n/a",
        "see #7200",  # a number that does not LEAD is not a hold
        "#7200 (open); none",  # a hold with a stray `none` NONE_YET does not read
    ],
)
def test_a_pr_field_that_is_not_none_yet_or_a_leading_number_is_a_finding(tmp_path, value):
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
    assert "docs/uplevel/roles/lane.md:10: token r157 is on two lanes' queues: ops-b and docs" in got  # fmt: skip


def test_two_cells_of_one_lane_are_two_queues(tmp_path):
    # ops-a and ops-b claim from their own rows (UR-52): one token on both is offered to both.
    roster = ROSTER.replace("`[r189]`, ", "`[r189]`, `[r157]`, ")
    got = findings(tmp_path, roster=roster)
    assert "docs/uplevel/roles/lane.md:9: token r157 is on two lanes' queues: ops-a and ops-b" in got  # fmt: skip


def test_the_operators_runs_are_not_claims(clean, tmp_path):
    # O2.5 is on ops-a's queue and the operator's (the operator RUNS it, ruling 188): not a finding,
    # because the operator's row lists runs (UR-15), not claims.
    assert ROSTER.count("`O2.5`") == 2 and "operator" in lint.RUNS
    # ...but a run of a package with no block anywhere is still check 1's finding.
    got = findings(tmp_path / "planted", roster=ROSTER.replace("`F2.3`'s batches, `O2.5`", "`F2.3`'s batches, `O2.5`, `[r999]`"))  # fmt: skip
    assert got == ["docs/uplevel/roles/lane.md:12: operator queue token r999 has no package block in docs/uplevel/packages/*.md"], got  # fmt: skip


def test_the_runs_list_and_the_unpackaged_lanes_are_exactly_the_named_ones():
    # RUNS is the operator alone: a lane added to it would stop check 3 counting a claim queue.
    assert frozenset({"operator"}) == lint.RUNS
    # UNPACKAGED is lane_tick's own list ("coordinator, heavy-a, heavy-b and operator"); a lane added
    # to it would have its tokens looked up anywhere instead of in the one file its digest reads.
    assert frozenset({"coordinator", "heavy", "operator"}) == lint.UNPACKAGED
    source = " ".join((UPLEVEL / "lane_tick.py").read_text(encoding="utf-8").split())
    assert "the roster's coordinator, heavy-a, heavy-b and operator rows have work that is never packaged" in source  # fmt: skip


def test_a_new_lane_with_no_file_is_an_unreadable_finding_not_an_unpackaged_lane(tmp_path):
    roster = ROSTER.replace("| `uplevel-docs`", "| `uplevel-new`         | fast      | `[r999]`                                           | none              |\n| `uplevel-docs`")  # fmt: skip
    got = findings(tmp_path, roster=roster)
    assert any(f.startswith("docs/uplevel/packages/new.md:1: unreadable") for f in got), got


# --- the real roster's shape -------------------------------------------------------------------


def real_tree(tmp_path: Path) -> tuple[Path, str]:
    """This checkout's roster, package files and ruling map, copied into ``tmp_path``."""
    rels = [lint.ROSTER_PATH, lint.MAP_PATH] + [
        p.relative_to(REPO_ROOT).as_posix()
        for p in sorted((REPO_ROOT / lint.PKGS_DIR).glob("*.md"))
    ]
    for rel in rels:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text((REPO_ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path, (tmp_path / lint.ROSTER_PATH).read_text(encoding="utf-8")


def plant_first(line: str, token: str) -> str:
    """The roster line with ``token`` as its queue cell's first entry (cell 3 of the row)."""
    cells = line.split("|")
    cells[3] = f" `[{token}]`," + cells[3]
    return "|".join(cells)


def test_on_the_real_roster_a_missing_token_is_caught_on_every_row(tmp_path):
    # Ruling 242: the real roster's own shape -- ruling 198's `none` on every row -- is what made
    # checks 1 and 3 check nothing, with a fixture whose labels were not `none` still green. So
    # this runs the lint on this checkout's real roster and package files, plants a token no block
    # carries as the first entry of EACH row, and asserts each plant is caught. It does not assert
    # that the real tree is clean: that stays CI's step, with its baseline (this file's docstring).
    root, roster = real_tree(tmp_path)
    rows = lint.roster_rows(roster)
    assert rows  # every row the real roster has, whatever its count or labels
    lines = roster.splitlines()
    for row in rows:
        planted = lines.copy()
        planted[row["line"] - 1] = plant_first(lines[row["line"] - 1], "r9999")
        (root / lint.ROSTER_PATH).write_text("\n".join(planted) + "\n", encoding="utf-8")
        got = [str(f) for f in lint.lint(lint.Disk(root))[0]]
        # The oracle is this checkout's files, not ``lint.UNPACKAGED``: a lane with its own package
        # file is looked up in that file alone, so a packaged lane wrongly added to that set reds
        # this test as well as the literal pin above (review R6 on #7221).
        own = lint.PKGS_PATH.format(row["lane"])
        where = own if (REPO_ROOT / own).is_file() else f"{lint.PKGS_DIR}/*.md"
        want = f"{lint.ROSTER_PATH}:{row['line']}: {row['name']} queue token r9999 has no package block in {where}"  # fmt: skip
        assert want in got, (row["name"], got)


def test_on_the_real_roster_a_token_on_heavy_as_queue_and_a_lanes_is_caught(tmp_path):
    root, roster = real_tree(tmp_path)
    rows = {r["name"]: r for r in lint.roster_rows(roster)}
    lines = roster.splitlines()
    for name in ("backend", "heavy-a"):
        n = rows[name]["line"] - 1
        lines[n] = plant_first(lines[n], "r9998")
    (root / lint.ROSTER_PATH).write_text("\n".join(lines) + "\n", encoding="utf-8")
    backend = root / lint.PKGS_PATH.format("backend")
    backend.write_text(backend.read_text(encoding="utf-8") + "\n### [r9998] planted\n\n**Flags:** none. **PR:** none yet.\n", encoding="utf-8")  # fmt: skip
    got = [str(f) for f in lint.lint(lint.Disk(root))[0]]
    assert f"{lint.ROSTER_PATH}:{rows['heavy-a']['line']}: token r9998 is on two lanes' queues: backend and heavy-a" in got, got  # fmt: skip


# --- 4. a ruling-map row without its record id ---------------------------------------------


@pytest.mark.parametrize(("ruling", "line"), [("146", 8), ("150", 10), ("176", 11), ("178", 13)])
def test_a_ruling_row_outside_the_pre_record_rows_needs_its_record_id(tmp_path, ruling, line):
    # Every row but 1-145 and 147: 146 and 148-176 carry ids on main too, so they are checked.
    rows = "\n".join(
        ln.split("(")[0].rstrip() + " |" if ln.startswith(f"| {ruling} ") else ln
        for ln in MAP.splitlines()
    )
    got = findings(tmp_path, map=rows + "\n")
    assert got == [f"docs/uplevel/history/ruling-map.md:{line}: ruling {ruling}'s row names no record id"]  # fmt: skip


def test_rows_1_to_145_and_147_and_owner_record_rows_are_not_checked(clean):
    # 1 and 147 carry no id in the fixture, as on main; owner-record rows are a different table,
    # keyed by the id itself.
    exempt = frozenset(range(1, 146)) | {147}
    assert exempt == lint.NO_RECORD_ID
    assert "| 147    | the plan rewrite (owner design session 2026-10-12) |" in MAP


def test_a_nine_or_eleven_digit_number_is_not_a_record_id(tmp_path):
    for digits in ("617242409", "61724240971"):
        rows = MAP.replace("6172424097", digits)
        assert findings(tmp_path, map=rows) == ["docs/uplevel/history/ruling-map.md:13: ruling 178's row names no record id"]  # fmt: skip


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
    got = [str(f) for f in lint.lint(lint.Disk(root))[0]]
    assert any(f.startswith("docs/uplevel/packages/docs.md:1: unreadable") for f in got), got


class Unreadable(lint.Disk):
    """A checkout whose ``docs.md`` is listed but cannot be read (a permission error, say)."""

    def read(self, rel: str) -> str:
        if rel.endswith("/docs.md"):
            raise PermissionError(13, "Permission denied")
        return super().read(rel)


def test_a_listed_but_unreadable_package_file_is_one_finding_not_three(tmp_path):
    # docs.md is read for docs' row, for the cross-file lookup (heavy-a, operator) and for check 2;
    # lint() reads each file once, so the failure is reported once.
    got = [str(f) for f in lint.lint(Unreadable(tree(tmp_path)))[0]]
    hits = [f for f in got if f.startswith("docs/uplevel/packages/docs.md:1: unreadable")]
    assert len(hits) == 1, got


# --- the CLI --------------------------------------------------------------------------------


def test_main_exits_0_on_a_clean_tree_and_says_what_it_read(tmp_path, capsys):
    assert lint.main(["--root", str(tree(tmp_path))]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out == ["plan_lint: 0 finding(s); read 8 roster rows, 4 package files (10 blocks), 7 ruling-map rows"]  # fmt: skip


def test_main_exits_1_with_one_file_line_per_finding(tmp_path, capsys):
    root = tree(tmp_path, docs=DOCS.replace("**PR:** none yet.", "**PR:** none\nyet."))
    assert lint.main(["--root", str(root)]) == 1
    out = capsys.readouterr().out.splitlines()
    assert len(out) == 2 and out[0].startswith("docs/uplevel/packages/docs.md:5: ")
    assert out[1].startswith("plan_lint: 1 finding(s);")


# --- the baseline: a PR fails only on what its base lacks ----------------------------------


class Base:
    """``git`` at one ref, answered from a dict of files -- the shape ``Ref`` reads it in."""

    def __init__(self, ref: str, tree_files: dict[str, str]) -> None:
        self.ref, self.files, self.calls = ref, tree_files, []

    def __call__(self, cmd):
        cmd = [str(c) for c in cmd]
        self.calls.append(cmd)
        assert cmd[0] == "git" and cmd[1] == "-C", cmd
        verb, args = cmd[3], cmd[4:]
        if verb == "rev-parse":
            if args[-1] != f"{self.ref}^{{commit}}":
                raise snap.CommandError("git rev-parse exited 1: no output")
            return "c" * 40 + "\n"
        if verb == "show":
            ref, _, rel = args[0].partition(":")
            if ref != self.ref or rel not in self.files:
                raise snap.CommandError(f"git show exited 128: fatal: path '{rel}' does not exist")
            return self.files[rel]
        if verb == "ls-tree":
            return "\n".join(p for p in sorted(self.files) if p.startswith(args[-1])) + "\n"
        raise AssertionError(f"unscripted git {cmd}")


def run_baseline(tmp_path, base_files, capsys, **head_over):
    root = tree(tmp_path, **head_over)
    base = Base("BASE", base_files)
    code = lint.main(["--root", str(root), "--baseline", "BASE"], run=base)
    return code, capsys.readouterr(), base


R184 = ROSTER.replace("`[r157]`, `[r172]`", "`[r157]`, `[r184]`, `[r172]`")


def test_a_defect_already_on_the_base_does_not_fail_the_pr(tmp_path, capsys):
    # main carries [r184] with no block; a PR that does not touch it must not go red for it.
    code, out, _ = run_baseline(tmp_path, files(roster=R184), capsys, roster=R184)
    assert code == 0
    assert "(already on BASE) docs/uplevel/roles/lane.md:9: ops-b queue token r184" in out.out
    assert "0 new finding(s) over BASE, 1 already there" in out.out


def test_an_old_defect_that_moved_lines_is_still_the_base_s(tmp_path, capsys):
    # Matched by file and message, not line: a row added above the defect moves it to line 10 (a
    # heavy-b row, as the real roster has: no tokens, so it adds no finding of its own).
    moved = R184.replace("| `uplevel-backend`", "| `uplevel-heavy-b`     | strongest | out of service (ruling 190)                        | none              |\n| `uplevel-backend`")  # fmt: skip
    code, out, _ = run_baseline(tmp_path, files(roster=R184), capsys, roster=moved)
    assert code == 0 and "lane.md:10: ops-b queue token r184" in out.out


def test_a_defect_the_pr_adds_fails_it_and_is_the_only_one_listed_as_new(tmp_path, capsys):
    wrapped = DOCS.replace("**PR:** none yet.", "**PR:** none\nyet.")
    code, out, _ = run_baseline(tmp_path, files(roster=R184), capsys, roster=R184, docs=wrapped)
    assert code == 1
    new = [ln for ln in out.out.splitlines() if not ln.startswith(("(already", "plan_lint:"))]
    assert new == [ln for ln in new if ln.startswith("docs/uplevel/packages/docs.md:5: [r165b]")] and len(new) == 1  # fmt: skip
    assert "1 new finding(s) over BASE, 1 already there" in out.out


def test_a_file_the_base_lacks_is_judged_as_wholly_new(tmp_path, capsys):
    base = {k: v for k, v in FILES.items() if not k.endswith("docs.md")}
    wrapped = DOCS.replace("**PR:** none yet.", "**PR:** none\nyet.")
    code, out, _ = run_baseline(tmp_path, base, capsys, docs=wrapped)
    assert code == 1 and "docs/uplevel/packages/docs.md:5: [r165b]" in out.out


def test_an_unreadable_baseline_judges_nothing(tmp_path, capsys):
    root = tree(tmp_path)
    code = lint.main(["--root", str(root), "--baseline", "nope"], run=Base("BASE", FILES))
    assert code == 2 and "baseline nope is unreadable" in capsys.readouterr().err


def test_over_baseline_counts_copies():
    f = lint.Finding("a.md", 3, "m")
    new, already = lint.over_baseline([f, f._replace(line=9)], [f])
    assert (len(new), len(already)) == (1, 1)


def test_the_baseline_reads_a_real_git_ref(tmp_path, capsys):
    # One end-to-end run through the real runner: commit a base with [r184], add a wrapped field
    # in the working tree, and only the field is new.
    def sh(*args):
        subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@t",
                        "-c", "commit.gpgsign=false", *args], check=True, capture_output=True)  # fmt: skip

    tree(tmp_path, roster=R184)
    sh("init", "-q")
    sh("add", "-A")
    sh("commit", "-q", "-m", "base")
    (tmp_path / "docs/uplevel/packages/docs.md").write_text(DOCS.replace("**PR:** none yet.", "**PR:** none\nyet."))  # fmt: skip
    assert lint.main(["--root", str(tmp_path), "--baseline", "HEAD"]) == 1
    out = capsys.readouterr().out
    assert "(already on HEAD) docs/uplevel/roles/lane.md:9: ops-b queue token r184" in out
    assert "1 new finding(s) over HEAD, 1 already there" in out


# --- the CI step -----------------------------------------------------------------------------


def ci_step() -> str:
    ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    return ci[ci.index("- name: Plan lint (ruling 197)") :].split("\n      - name:", 1)[0]


def test_ci_runs_the_lint_with_the_merge_commits_first_parent_as_its_baseline():
    # The real tree is judged in CI, not in this suite: collection-sanity runs the lint on a PR
    # with the checked-out merge commit's FIRST parent as --baseline -- the main the run merged
    # into -- and with no baseline on a push to main. pull_request.base.sha is main as of the PR's
    # last update, so a defect that reached main since would read as the PR's own.
    step = ci_step()
    assert "pull_request.base.sha" not in step
    assert "EVENT: ${{ github.event_name }}" in step and '[ "${EVENT}" = "pull_request" ]' in step
    assert "git cat-file -p HEAD" in step
    assert 'git fetch --no-tags --depth=1 origin "${BASE_SHA}"' in step
    assert 'python -m scripts.uplevel.plan_lint --baseline "${BASE_SHA}"' in step
    assert step.count("python -m scripts.uplevel.plan_lint") == 2  # with and without a baseline
    # fail closed: no parent to read a baseline from is exit 2 with its reason, never a full lint
    assert "exit 2" in step and "no baseline, nothing judged" in step


def test_the_steps_base_line_reads_the_first_parent_in_a_depth_1_clone(tmp_path):
    # The step's premise, run for real: in a depth-1 checkout of a merge commit the parents are
    # not fetched, yet `git cat-file -p HEAD` still names them (it prints the raw object), and the
    # step's own line takes the FIRST -- the main side of the merge.
    line = next(ln.strip() for ln in ci_step().splitlines() if ln.strip().startswith('BASE_SHA="$('))  # fmt: skip
    src, clone = tmp_path / "src", tmp_path / "clone"

    def sh(*args, cwd=src):
        return subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
            cwd=cwd, check=True, capture_output=True, text=True,
        ).stdout.strip()  # fmt: skip

    src.mkdir()
    sh("init", "-q", "-b", "main")
    sh("commit", "-q", "--allow-empty", "-m", "base")
    sh("checkout", "-q", "-b", "pr")
    sh("commit", "-q", "--allow-empty", "-m", "pr work")
    sh("checkout", "-q", "main")
    sh("commit", "-q", "--allow-empty", "-m", "main moved on")
    main_tip = sh("rev-parse", "HEAD")
    sh("merge", "-q", "--no-ff", "-m", "merge pr into main", "pr")
    sh("clone", "-q", "--depth=1", f"file://{src}", str(clone), cwd=tmp_path)
    assert sh("rev-parse", "--is-shallow-repository", cwd=clone) == "true"
    got = subprocess.run(["bash", "-c", f'set -euo pipefail\n{line}\necho "$BASE_SHA"'], cwd=clone,
                         check=True, capture_output=True, text=True).stdout.strip()  # fmt: skip
    assert got == main_tip
