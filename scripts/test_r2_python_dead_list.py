#!/usr/bin/env python3
"""Tests for scripts/r2-python-dead-list.py (O2.3b / ruling 73).

Run explicitly; outside testpaths (like every scripts/test_*.py gate suite):

    uv run python -m pytest scripts/test_r2_python_dead_list.py -q

The generator writes R2's Python "modules serving no feature" input into
marker regions of docs/reference/feature-inventory.md (§4) and
docs/uplevel/r2-sheet.md (§3). This suite is the FRESHNESS GATE: the
committed regions must equal what the tool produces right now. A stale R2
input is how B3.2 deletes a file that started shipping (or keeps a file
that stopped) — same "gate with no CI rots" logic that put every other
scripts gate in the battery.

The git-history column is masked in the comparison, not recomputed: the
battery job's checkout is depth-1 (measured: 30 of 31 ci.yml checkouts
carry no fetch-depth), and `git log -- path` over one commit knows
nothing. It is format-validated here and compared in full wherever full
history exists (the pre-commit hook and any full clone running the tool
with --check). Everything else — membership, lines, exceptions, the
tool-inputs stamp, the r2-sheet prose — is recomputed and compared
exactly.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GENERATOR = REPO_ROOT / "scripts" / "r2-python-dead-list.py"


def _load():
    spec = importlib.util.spec_from_file_location("r2_python_dead_list", GENERATOR)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gen = _load()


@pytest.fixture(scope="module")
def fresh() -> dict:
    """One full walk of the real tree (same shared-walk cost pattern as
    test_reachability.py's real_out; every consumer carries the mark)."""
    reach_mod = importlib.util.spec_from_file_location(
        "reachability", REPO_ROOT / "scripts" / "reachability.py"
    )
    reach = importlib.util.module_from_spec(reach_mod)
    reach_mod.loader.exec_module(reach)
    entries, allow = reach.load_entry_points(reach.DEFAULT_ENTRIES)
    keep = reach.load_keep(reach.DEFAULT_KEEP)
    out = reach.analyze(
        REPO_ROOT,
        entries=entries,
        candidate_dirs=reach.DEFAULT_CANDIDATE_DIRS,
        keep=keep,
        dynamic_allow=allow,
    )
    dead = {m["module"]: m["lines"] for m in out["not_shipping"]}
    claimed = gen.claimed_by_rows()
    stamp = gen._walker_hash()
    table, listed, listed_lines = gen.build_table(dead, claimed, stamp, history=False)
    prose = gen.build_r2_prose(listed, listed_lines, dead, claimed, stamp)
    inv_region = gen._region(gen.INVENTORY.read_text(encoding="utf-8"))
    r2_region = gen._region(gen.R2_SHEET.read_text(encoding="utf-8"))
    return {
        "out": out,
        "dead": dead,
        "claimed": claimed,
        "stamp": stamp,
        "table": table,
        "prose": prose,
        "inv_region": inv_region,
        "r2_region": r2_region,
    }


@pytest.mark.timeout(120)
def test_committed_inventory_table_is_fresh(fresh):
    """The gate: inventory §4's Python region == the tool's current output
    (history column masked, see module docstring)."""
    assert gen._mask_history(fresh["inv_region"]).strip() == gen._mask_history(
        fresh["table"]
    ).strip(), "R2 Python input is stale: run uv run python scripts/r2-python-dead-list.py"


@pytest.mark.timeout(120)
def test_committed_r2_sheet_prose_is_fresh(fresh):
    """No history column in the sheet's prose at all — exact comparison."""
    assert fresh["r2_region"].strip() == fresh["prose"].strip(), (
        "r2-sheet §3 Python prose is stale: run the generator"
    )


@pytest.mark.timeout(120)
def test_stamp_in_regions_matches_tool_inputs(fresh):
    for region in (fresh["inv_region"], fresh["r2_region"]):
        m = re.search(r"Measured at tool-inputs `([0-9a-f]{10})`", region)
        assert m, "region header must carry the tool-inputs stamp"
        assert m.group(1) == fresh["stamp"], "stamp drifted: inputs changed, table not regenerated"


@pytest.mark.timeout(120)
def test_history_column_is_well_formed(fresh):
    """The masked column's substitute: every list row carries a real
    `sha` YYYY-MM-DD cell (a literal '-' is the documented none-found
    value). Full comparison happens where history exists."""
    problems = gen._history_format_problems(fresh["inv_region"])
    assert not problems, problems


@pytest.mark.timeout(120)
def test_no_ancestor_of_a_shipping_module_is_listed(fresh):
    """The ruling-73 property, checked ON THE TABLE (not just the model):
    no row may name a parent __init__ of a shipping module — the import
    system runs it, so the deletion list must not carry it."""
    shipping = set(fresh["out"]["shipping"])
    anc: set[str] = set()
    for rel in shipping:
        parts = rel.split("/")
        for i in range(1, len(parts)):
            anc.add("/".join(parts[:i]) + "/__init__.py")
    rows = set(re.findall(r"^\| `([^`]+)` \| \w+ \| \d+ \|", fresh["inv_region"], flags=re.M))
    leaked = sorted(r for r in rows if r in anc)
    assert not leaked, f"ancestor packages of shipping modules on the deletion list: {leaked}"


@pytest.mark.timeout(120)
def test_claimed_modules_are_named_as_exceptions_not_listed(fresh):
    body, _, ex_block = fresh["inv_region"].partition("Claimed by a row")
    listed_rows = set(re.findall(r"^\| `([^`]+)` \| \w+ \|", body, flags=re.M))
    ex_rows = set(re.findall(r"^\| `([^`]+)` \|", ex_block, flags=re.M))
    expected_ex = set(fresh["dead"]) & set(fresh["claimed"])
    assert ex_rows == expected_ex
    assert not (listed_rows & expected_ex), "a claimed module must not also sit on the list"


# ------------------------------------------------- generator unit pins --


def test_claims_parser_reads_modules_column_not_evidence():
    """A row CLAIMS the paths in its `modules` column; the same path cited
    in the `backend` (evidence) column is not a claim — and a header with
    the columns swapped still resolves by name."""
    header = "| id | surface | modules | backend | status |\n| --- | --- | --- | --- | --- |\n"
    row = (
        "| F-001 | X | `backend/services/claimed.py` | "
        "does `backend/services/evidence.py:12` | unverified |\n"
    )
    claims = gen._claims_from_text(header + row)
    assert set(claims) == {"backend/services/claimed.py"}
    assert claims["backend/services/claimed.py"] == ["F-001"]

    swapped = "| id | surface | backend | modules | status |\n| --- | --- | --- | --- | --- |\n"
    row2 = (
        "| F-002 | Y | `backend/services/evidence.py:12` | "
        "`backend/services/claimed2.py`, `ai/other.py:3-9` | unverified |\n"
    )
    claims2 = gen._claims_from_text(swapped + row2)
    assert set(claims2) == {"backend/services/claimed2.py", "ai/other.py"}


def test_build_table_partitions_claims_and_carries_tool_counts():
    dead = {
        "backend/services/kept.py": 10,
        "backend/pkg/dead_a.py": 7,
        "ai/dead_b.py": 3,
        "synthbench/pkg/__init__.py": 1,
    }
    claimed = {"backend/services/kept.py": ["F-042"]}
    table, listed, lines = gen.build_table(dead, claimed, "abc123def4", history=False)
    assert listed == 3 and lines == 11
    body, _, ex_block = table.partition("Claimed by a row")
    assert "kept.py" not in body.split("Claimed")[0]
    assert "| `backend/services/kept.py` | 10 | F-042 |" in ex_block
    assert "| `ai/dead_b.py` | ai | 3 |" in body
    assert "| `synthbench/pkg/__init__.py` | synthbench | 1 |" in body
