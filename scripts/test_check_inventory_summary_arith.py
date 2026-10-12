#!/usr/bin/env python3
"""Tests for scripts/check-inventory-summary-arith.py (the §2 census gate).

Run explicitly; outside testpaths:

    uv run python -m pytest scripts/test_check_inventory_summary_arith.py -q

The §2 summary table of docs/reference/feature-inventory.md was, until this
checker existed, compared to nothing. A gate for it is only real if it reddens,
so almost every test here is a MUTANT of a small fixture doc rather than an
assertion about the real one. Two rules keep the fixtures honest:

  * the expected §2 numbers are computed from the fixture's own (id, status)
    TUPLES, never by re-parsing the rows the fixture just rendered — a helper
    that parsed its own output would inherit the very split bug it is meant to
    catch, and then the escaped-pipe arm could not fail;
  * one arm must PASS (a cell containing an escaped pipe, which the real F-006
    carries). A parser that split on `\\|` would invent a column, shift `status`
    right, and read prose as a count while still exiting 0 on a plain doc — so
    green on the ordinary cases proves nothing about that failure mode.

Hazards pinned below are the three the real document actually carries: escaped
pipes inside cells, per-section tables whose column ORDER nothing fixes, and a
status vocabulary that lives in the summary header instead of in code.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "check-inventory-summary-arith.py"
REAL_DOC = REPO_ROOT / "docs" / "reference" / "feature-inventory.md"

STATUSES = ["unverified", "half-built", "leftover", "awaiting real tier"]
ROW_HEADER = ("| id | surface | action | API calls | backend | status | evidence "
              "| modules | real tier | ruling | priority |")
ROW_SEP = "| " + " | ".join(["---"] * 11) + " |"
SUMMARY_HEADER = "| section | rows | " + " | ".join(STATUSES) + " |"
SUMMARY_SEP = "| --- | --- | " + " | ".join("---" for _ in STATUSES) + " |"


def cells(rows: list[tuple[str, str]], bold: bool = False) -> list[str]:
    """The §2 numbers a correct summary must carry for these rows, from the tuples."""
    counts: dict[str, int] = {}
    for spec in rows:
        counts[spec[1]] = counts.get(spec[1], 0) + 1
    out = [str(len(rows))] + [str(counts.get(s, 0)) for s in STATUSES]
    return [f"**{c}**" for c in out] if bold else out


def summary_row(num: str, rows: list[tuple[str, str]], bold: bool = False) -> str:
    return f"| [3.{num} Section {num}](#3{num.replace('.', '')}-section-{num}) | " \
           f"{' | '.join(cells(rows, bold))} |"


def row(spec: tuple[str, str] | tuple[str, str, str]) -> str:
    row_id, status = spec[0], spec[1]
    action = spec[2] if len(spec) > 2 else "views the panel"
    return (f"| {row_id} | Some surface | {action} | GET /x | app.py:1 | {status} "
            "| why | mod.py | — | complete | p1 |")


def doc(sections: dict[str, list[tuple[str, str]]], *, all_row: str | None = None) -> str:
    """A whole inventory doc whose §2 agrees with §3 unless a caller breaks it."""
    if all_row is None:
        every = [r for rows in sections.values() for r in rows]
        all_row = "| **all** | " + " | ".join(cells(every, bold=True)) + " |"
    body = (
        "## 2. Summary\n\n" + SUMMARY_HEADER + "\n" + SUMMARY_SEP + "\n"
        + "\n".join(summary_row(n, rows) for n, rows in sections.items())
        + "\n" + all_row + "\n"
    )
    parts = []
    for num, rows in sections.items():
        parts.append(
            f"### 3.{num} Section {num}\n\n{ROW_HEADER}\n{ROW_SEP}\n"
            + "\n".join(row(spec) for spec in rows) + "\n"
        )
    return "## 1. Preamble\n\nProse.\n\n" + body + "\n## 3. Sections\n\n" + "".join(parts)


def run(path: Path) -> tuple[int, str, dict | None]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), str(path), "--json"],
        capture_output=True, text=True, check=False,
    )
    payload = json.loads(proc.stdout) if proc.stdout.strip().startswith("{") else None
    return proc.returncode, proc.stdout + proc.stderr, payload


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "feature-inventory.md"
    path.write_text(text, encoding="utf-8")
    return path


TWO = {
    "1": [("F-001", "unverified"), ("F-002", "half-built"), ("F-003", "half-built")],
    "2": [("F-010", "leftover"), ("F-011", "awaiting real tier")],
}


# ---------------------------------------------------------------- happy path


def test_agreeing_doc_passes(tmp_path):
    rc, out, payload = run(write(tmp_path, doc(TWO)))
    assert rc == 0, out
    assert payload["rows"] == 5 and payload["sections_derived"] == 2, payload


def test_real_inventory_agrees():
    """Walk-on-real-data: the shipped doc must satisfy the shipped gate."""
    rc, out, payload = run(REAL_DOC)
    assert rc == 0, out
    assert payload["sections_derived"] == 13, payload
    assert payload["rows"] > 250, payload


# ------------------------------------------------- mutants that must go RED


def test_stale_summary_cell_is_caught(tmp_path):
    """THE defect this gate exists for: rows changed status, §2 did not follow.

    Halving one cell is scored against the derived rows, so it drifts exactly
    one cell — and the message must name which tier, or a reader cannot act.
    """
    base = doc(TWO)
    broken = base.replace("| 3 | 1 | 2 | 0 | 0 |", "| 3 | 1 | 1 | 0 | 0 |")
    assert broken != base, "fixture edit missed — the mutant is a no-op"
    rc, out, payload = run(write(tmp_path, broken))
    assert rc == 1, f"a stale §2 cell passed the gate: {out}"
    assert payload["drift_cells"] == 1, payload
    assert "half-built: published 1, derived from rows 2" in payload["drift"][0], payload


def test_stale_all_row_is_caught(tmp_path):
    """`all` drifting from the column sums is a different bug from a section row
    drifting, so it needs its own arm."""
    base = doc(TWO)
    broken = base.replace("| **all** | **5** |", "| **all** | **6** |")
    assert "| **all** | **6** |" in broken, "fixture edit missed"
    rc, out, payload = run(write(tmp_path, broken))
    assert rc == 1, f"a stale all-row passed the gate: {out}"
    assert any(d.startswith("all rows") for d in payload["drift"]), payload


def test_summary_row_for_a_deleted_section_is_caught(tmp_path):
    """§2 advertising a section §3 no longer has must not tally silently."""
    base = doc(TWO)
    broken = "\n".join(l for l in base.splitlines() if "(#32-section-2)" not in l)
    assert "(#32-section-2)" not in broken.split("## 3.")[0], "fixture edit missed"
    rc, out, payload = run(write(tmp_path, broken))
    assert rc == 1, f"an orphan §2 row was accepted: {out}"
    assert payload["sections_published"] == 1, payload
    assert payload["sections_derived"] == 2, payload


def test_new_status_without_a_column_is_caught(tmp_path):
    """A row given a tier the summary has no column for must FAIL, not be
    skipped: a checker tallying only known columns silently loses rows."""
    rc, out, payload = run(write(tmp_path, doc({"1": [("F-001", "unverified"),
                                                      ("F-002", "shipped")]})))
    assert rc == 1, f"an unlisted status vanished from the count: {out}"
    assert "shipped" in out, payload


def test_duplicate_id_is_a_failure_not_a_count(tmp_path):
    """Renumbering can put one id in two sections; summing both double-counts."""
    rc, out, _ = run(write(tmp_path, doc({"1": [("F-001", "unverified")],
                                          "2": [("F-001", "leftover")]})))
    assert rc == 2, f"a duplicated id was scored instead of refused: {out}"
    assert "duplicate id" in out, out


def test_missing_summary_table_is_a_failure(tmp_path):
    """An absent table must NOT look like an empty pass."""
    rc, out, _ = run(write(tmp_path, doc(TWO).replace("## 2. Summary", "## 2. Rollup")))
    assert rc == 2, f"a doc with no §2 table passed: {out}"


def test_section_losing_its_id_column_is_refused(tmp_path):
    """A renamed header column would drop the whole table's rows from the tally."""
    rc, out, _ = run(write(tmp_path, doc(TWO).replace("| id | surface", "| ident | surface")))
    assert rc == 2, f"a section whose table lost `id` was skipped: {out}"


def test_non_row_line_in_a_table_is_refused_not_dropped(tmp_path):
    """A `|`-led line whose first cell is not an `F-nnn` used to be skipped in
    silence, and silence here is the gate's worst failure: the skip removes the
    line from §3's tally while §2 keeps whatever it published, so a stale §2 and a
    shrunken §3 agree and the checker exits 0 on the arithmetic it exists to
    police. Refusing is the only honest option — the checker cannot know whether
    the line was meant to be a row."""
    text = doc(TWO)
    intruder = "| see the note below | prose | absorbed | — | — | half-built | — | — | — | — | — |\n"
    anchor = row(TWO["1"][0]) + "\n"
    assert anchor in text, "fixture row anchor missing — the mutation would be a no-op"
    text = text.replace(anchor, anchor + intruder, 1)
    assert intruder in text, "intruder line not inserted — arm is a no-op"
    rc, out, _ = run(write(tmp_path, text))
    assert rc == 2, f"a non-row table line was dropped from both denominators: {out}"
    assert "would be dropped from BOTH denominators" in out, out


def test_reordered_columns_still_score_the_right_column(tmp_path):
    """Columns resolve by NAME, so a reordered §3 table must still agree. A
    split-index parser would tally the `evidence` column and print plausible
    integers while being wrong."""
    one = {"1": [("F-001", "unverified"), ("F-002", "half-built")]}
    text = doc(one)
    swapped_header = ("| id | status | surface | action | API calls | backend | evidence "
                      "| modules | real tier | ruling | priority |")
    text = text.replace(ROW_HEADER, swapped_header)
    for spec in one["1"]:
        rid, status = spec
        before = f"| {rid} | Some surface | views the panel | GET /x | app.py:1 | {status} "
        after = f"| {rid} | {status} | Some surface | views the panel | GET /x | app.py:1 "
        assert before in text, f"fixture row for {rid} did not match — arm is a no-op"
        text = text.replace(before, after)
    rc, out, payload = run(write(tmp_path, text))
    assert rc == 0, f"a column reorder broke the gate: {out}"
    assert payload["rows"] == 2, payload
    assert payload["statuses"] == {"unverified": 1, "half-built": 1, "leftover": 0,
                                   "awaiting real tier": 0}, payload


# --------------------------------------------- the mutant that must stay GREEN


def test_escaped_pipe_inside_a_cell_is_not_a_column(tmp_path):
    """The real F-006 carries `42% \\| 61°C` in its action cell. A parser that
    split on every pipe would invent a column, shift `status` right of it, and
    start reading prose as a status — visible here and nowhere else, because an
    ordinary doc scores correctly under the broken parser too."""
    one = {"1": [("F-001", "half-built", "shows `42% \\| 61°C` thresholds")]}
    rc, out, payload = run(write(tmp_path, doc(one)))
    assert rc == 0, f"an escaped pipe was read as a column break: {out}"
    assert payload["statuses"] == {"unverified": 0, "half-built": 1, "leftover": 0,
                                   "awaiting real tier": 0}, payload
