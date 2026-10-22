#!/usr/bin/env python3
"""Tests for scripts/check-inventory-summary-arith.py (ruling 251: §2 is computed, not stored).

Run explicitly; outside testpaths:

    uv run python -m pytest scripts/test_check_inventory_summary_arith.py -q

The script prints docs/reference/feature-inventory.md's §2 table from the §3 rows. Until
ruling 251 §2 was a hand-kept copy this script checked; now the document stores none, and
the script refuses a stored copy coming back. Almost every test here is a MUTANT of a small
fixture doc rather than an assertion about the real one. Two rules keep the fixtures honest:

  * the expected numbers are computed from the fixture's own (id, status) TUPLES, never by
    re-parsing the rows the fixture just rendered -- a helper that parsed its own output
    would inherit the very split bug it is meant to catch, and then the escaped-pipe arm
    could not fail;
  * one arm must PASS (a cell containing an escaped pipe, which the real F-006 carries). A
    parser that split on `\\|` would invent a column, shift `status` right, and read prose
    as a status while still exiting 0 on a plain doc.

Hazards pinned below are the ones the real document carries: escaped pipes inside cells,
per-section tables whose column ORDER nothing fixes, and a status vocabulary that lives in
the document's own legend (§1, `### Statuses`) instead of in code.
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
ROW_HEADER = (
    "| id | surface | action | API calls | backend | status | evidence "
    "| modules | real tier | ruling | priority |"
)
ROW_SEP = "| " + " | ".join(["---"] * 11) + " |"
LEGEND = "### Statuses\n\n| status | meaning here |\n| --- | --- |\n" + "".join(
    f"| **{s}** | what {s} means |\n" for s in STATUSES
)
SUMMARY = "## 2. Summary\n\nComputed, not stored (ruling 251).\n\n"


def counts(rows: list[tuple[str, ...]]) -> list[str]:
    """The numbers a correct table carries for these rows, from the tuples."""
    tally: dict[str, int] = {}
    for spec in rows:
        tally[spec[1]] = tally.get(spec[1], 0) + 1
    return [str(len(rows))] + [str(tally.get(s, 0)) for s in STATUSES]


def expected_table(sections: dict[str, list[tuple[str, ...]]]) -> list[str]:
    out = [
        "| section | rows | " + " | ".join(STATUSES) + " |",
        "| --- | --- | " + " | ".join("---" for _ in STATUSES) + " |",
    ]
    for num, rows in sections.items():
        out.append(
            f"| [3.{num} Section {num}](#3{num}-section-{num}) | " + " | ".join(counts(rows)) + " |"
        )
    every = [r for rows in sections.values() for r in rows]
    out.append("| **all** | " + " | ".join(f"**{c}**" for c in counts(every)) + " |")
    return out


def row(spec: tuple[str, ...]) -> str:
    row_id, status = spec[0], spec[1]
    action = spec[2] if len(spec) > 2 else "views the panel"
    return (
        f"| {row_id} | Some surface | {action} | GET /x | app.py:1 | {status} "
        "| why | mod.py | — | complete | p1 |"
    )


def doc(sections: dict[str, list[tuple[str, ...]]]) -> str:
    """A whole inventory doc: the legend, a §2 with no table, and the §3 sections."""
    parts = []
    for num, rows in sections.items():
        parts.append(
            f"### 3.{num} Section {num}\n\n{ROW_HEADER}\n{ROW_SEP}\n"
            + "\n".join(row(spec) for spec in rows)
            + "\n"
        )
    return (
        "## 1. How to read this document\n\n"
        + LEGEND
        + "\nProse.\n\n"
        + SUMMARY
        + "## 3. Sections\n\n"
        + "".join(parts)
    )


def run(path: Path, *, as_json: bool = True) -> tuple[int, str, dict | None]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), str(path), *(["--json"] if as_json else [])],
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(proc.stdout) if as_json and proc.stdout.strip().startswith("{") else None
    return proc.returncode, proc.stdout + proc.stderr, payload


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "feature-inventory.md"
    path.write_text(text, encoding="utf-8")
    return path


TWO = {
    "1": [("F-001", "unverified"), ("F-002", "half-built"), ("F-003", "half-built")],
    "2": [("F-010", "leftover"), ("F-011", "awaiting real tier")],
}


# ---------------------------------------------------------------- the printed table


def test_the_printed_table_is_the_rows_counts(tmp_path):
    rc, out, _ = run(write(tmp_path, doc(TWO)), as_json=False)
    assert rc == 0, out
    assert out.splitlines() == expected_table(TWO), out


def test_the_json_census_counts_the_rows(tmp_path):
    rc, out, payload = run(write(tmp_path, doc(TWO)))
    assert rc == 0, out
    assert payload["rows"] == 5 and payload["sections_derived"] == 2, payload
    assert payload["statuses"] == {
        "unverified": 1,
        "half-built": 2,
        "leftover": 1,
        "awaiting real tier": 1,
    }, payload
    assert payload["sections"]["3.2"] == {
        "rows": 2,
        "unverified": 0,
        "half-built": 0,
        "leftover": 1,
        "awaiting real tier": 1,
    }, payload


def test_sections_print_in_numeric_order_not_text_order(tmp_path):
    """`3.10` sorts before `3.2` as text; the real document has both."""
    sections = {str(n): [(f"F-{n:03d}", "unverified")] for n in (1, 2, 10)}
    text = doc(sections)
    rc, out, _ = run(write(tmp_path, text), as_json=False)
    assert rc == 0, out
    firsts = [ln.split("]")[0] for ln in out.splitlines() if ln.startswith("| [3.")]
    assert firsts == ["| [3.1 Section 1", "| [3.2 Section 2", "| [3.10 Section 10"], out


def test_real_inventory_prints_and_passes():
    """The shipped doc: 13 sections, the legend's five statuses, and no stored §2."""
    rc, out, payload = run(REAL_DOC)
    assert rc == 0, out
    assert payload["sections_derived"] == 13, payload
    assert payload["rows"] > 250, payload
    assert list(payload["statuses"]) == [
        "unverified",
        "half-built",
        "leftover",
        "awaiting real tier",
        "works",
    ], payload
    assert sum(payload["statuses"].values()) == payload["rows"], payload
    rc, table, _ = run(REAL_DOC, as_json=False)
    assert rc == 0, table
    assert table.splitlines()[-1].startswith(f"| **all** | **{payload['rows']}** |"), table


# ------------------------------------------------- mutants that must go RED


def test_a_status_outside_the_legend_is_a_failure(tmp_path):
    """A row given a tier the legend does not name must FAIL, not be skipped: a
    tally of only known statuses silently loses rows."""
    rc, out, payload = run(
        write(tmp_path, doc({"1": [("F-001", "unverified"), ("F-002", "shipped")]}))
    )
    assert rc == 1, f"an unlisted status vanished from the count: {out}"
    assert "shipped" in out and "legend" in out, payload


def test_a_stored_summary_table_is_a_failure(tmp_path):
    """Ruling 251: §2 stores no table. One coming back (a rebase that kept an old
    hunk) is the hand-kept copy again, so it fails and says what to do."""
    stored = "\n".join(expected_table(TWO)) + "\n\n"
    text = doc(TWO).replace(SUMMARY, SUMMARY + stored, 1)
    assert stored in text, "arm is a no-op"
    rc, out, payload = run(write(tmp_path, text))
    assert rc == 1, f"a stored §2 table was accepted: {out}"
    assert any("ruling 251" in p for p in payload["problems"]), payload


def test_a_table_after_section_2_is_not_a_stored_summary(tmp_path):
    """The guard reads §2's body only: §3's own tables are not a stored summary."""
    rc, out, _ = run(write(tmp_path, doc(TWO)))
    assert rc == 0, out


def test_a_doc_without_a_legend_is_refused(tmp_path):
    rc, out, _ = run(write(tmp_path, doc(TWO).replace("### Statuses", "### Status words", 1)))
    assert rc == 2, f"a doc with no legend was scored: {out}"
    assert "no '### Statuses' heading" in out, out


def test_a_legend_without_a_status_column_is_refused(tmp_path):
    rc, out, _ = run(
        write(tmp_path, doc(TWO).replace("| status | meaning here |", "| tier | meaning here |", 1))
    )
    assert rc == 2, f"a legend with no `status` column was read: {out}"
    assert "no `status` column" in out, out


def test_a_legend_naming_no_status_is_refused(tmp_path):
    """A legend with its header and separator but no status row is read, then refused."""
    text = doc(TWO)
    for s in STATUSES:
        text = text.replace(f"| **{s}** | what {s} means |\n", "", 1)
    rc, out, _ = run(write(tmp_path, text))
    assert rc == 2, f"an empty legend was read as a vocabulary: {out}"
    assert "names no status" in out, out


def test_a_section_number_used_twice_is_refused(tmp_path):
    """Two `### 3.2` headings: the later copy would replace the earlier, and its rows
    would vanish from the table and the `all` row with rc 0. The stored §2 used to
    catch this by disagreeing; now the script refuses it."""
    text = doc(
        {
            "1": [("F-001", "unverified")],
            "2": [("F-010", "leftover")],
            "3": [("F-020", "half-built")],
        }
    ).replace("### 3.3 Section 3", "### 3.2 Section 3", 1)
    assert text.count("### 3.2 ") == 2, "arm is a no-op"
    rc, out, _ = run(write(tmp_path, text))
    assert rc == 2, f"a duplicated section number was tallied: {out}"
    assert "appears twice" in out, out


def test_a_heading_with_punctuation_links_to_githubs_anchor(tmp_path):
    """The real headings carry `:`, `,` and `-` (3.5, 3.10, 3.12); the expected slug is
    written out by hand, not computed by the code under test."""
    text = doc(TWO).replace("### 3.1 Section 1", "### 3.1 Settings: cameras, rules (and re-ID)", 1)
    rc, out, _ = run(write(tmp_path, text), as_json=False)
    assert rc == 0, out
    assert (
        "| [3.1 Settings: cameras, rules (and re-ID)](#31-settings-cameras-rules-and-re-id) |"
        in out
    ), out


def test_the_real_inventorys_links_are_the_ones_its_stored_table_used():
    """Three anchors the hand-kept §2 carried before ruling 251, as GitHub rendered them."""
    rc, out, _ = run(REAL_DOC, as_json=False)
    assert rc == 0, out
    for slug in (
        "#35-alerts-entities-and-re-id",
        "#310-settings-cameras-rules-processing-notifications-access",
        "#312-zones-plates-household-faces-heatmaps-scene-changes-tracks",
    ):
        assert f"]({slug}) |" in out, (slug, out)


def test_a_failure_exits_1_in_text_mode_too(tmp_path):
    rc, out, _ = run(write(tmp_path, doc({"1": [("F-001", "shipped")]})), as_json=False)
    assert rc == 1, f"text mode passed a status outside the legend: {out}"
    assert "legend" in out, out


def test_a_renamed_section_2_heading_still_guards_its_body(tmp_path):
    stored = "\n".join(expected_table(TWO)) + "\n\n"
    text = doc(TWO).replace(SUMMARY, "## 2. Summary (computed)\n\n" + stored, 1)
    rc, out, payload = run(write(tmp_path, text))
    assert rc == 1, f"a stored table under a renamed §2 heading was accepted: {out}"
    assert any("ruling 251" in p for p in payload["problems"]), payload


def test_a_doc_without_a_section_2_heading_is_refused(tmp_path):
    rc, out, _ = run(write(tmp_path, doc(TWO).replace(SUMMARY, "", 1)))
    assert rc == 2, f"a doc with no `## 2.` heading was scored: {out}"
    assert "no '## 2.' heading" in out, out


def test_two_legend_tables_are_refused(tmp_path):
    second = "| status | meaning here |\n| --- | --- |\n| **shipped** | a second vocabulary |\n"
    text = doc(TWO).replace("\nProse.\n", "\n" + second + "\nProse.\n", 1)
    assert second in text, "arm is a no-op"
    rc, out, _ = run(write(tmp_path, text))
    assert rc == 2, f"a second legend table was ignored: {out}"
    assert "found 2" in out, out


def test_a_wrapped_prose_line_starting_with_a_hash_does_not_end_the_legend(tmp_path):
    """The inventory wraps prose onto lines like `#6854) ...`; only a real heading
    (`#` to `######` then a space) ends the legend's body."""
    text = doc(TWO).replace(
        "### Statuses\n\n", "### Statuses\n\nAs ruled on\n#6854) the vocabulary is:\n\n", 1
    )
    rc, out, _ = run(write(tmp_path, text))
    assert rc == 0, f"a wrapped `#NNNN)` line cut the legend off: {out}"


def test_duplicate_id_is_a_failure_not_a_count(tmp_path):
    """Renumbering can put one id in two sections; summing both double-counts."""
    rc, out, _ = run(
        write(tmp_path, doc({"1": [("F-001", "unverified")], "2": [("F-001", "leftover")]}))
    )
    assert rc == 2, f"a duplicated id was scored instead of refused: {out}"
    assert "duplicate id" in out, out


def test_section_losing_its_id_column_is_refused(tmp_path):
    """A renamed header column would drop the whole table's rows from the tally."""
    rc, out, _ = run(write(tmp_path, doc(TWO).replace("| id | surface", "| ident | surface")))
    assert rc == 2, f"a section whose table lost `id` was skipped: {out}"


def test_non_row_line_in_a_table_is_refused_not_dropped(tmp_path):
    """A `|`-led line whose first cell is not an `F-nnn` used to be skipped in
    silence, and silence here is the gate's worst failure: the skip removes the
    line from §3's tally, and the printed table is wrong with nothing to compare
    it against. Refusing is the only honest option — the checker cannot know
    whether the line was meant to be a row."""
    text = doc(TWO)
    intruder = (
        "| see the note below | prose | absorbed | — | — | half-built | — | — | — | — | — |\n"
    )
    anchor = row(TWO["1"][0]) + "\n"
    assert anchor in text, "fixture row anchor missing — the mutation would be a no-op"
    text = text.replace(anchor, anchor + intruder, 1)
    assert intruder in text, "intruder line not inserted — arm is a no-op"
    rc, out, _ = run(write(tmp_path, text))
    assert rc == 2, f"a non-row table line was dropped from both denominators: {out}"
    assert "would be dropped from the census" in out, out


def test_reordered_columns_still_score_the_right_column(tmp_path):
    """Columns resolve by NAME, so a reordered §3 table must still agree. A
    split-index parser would tally the `evidence` column and print plausible
    integers while being wrong."""
    one = {"1": [("F-001", "unverified"), ("F-002", "half-built")]}
    text = doc(one)
    swapped_header = (
        "| id | status | surface | action | API calls | backend | evidence "
        "| modules | real tier | ruling | priority |"
    )
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
    assert payload["statuses"] == {
        "unverified": 1,
        "half-built": 1,
        "leftover": 0,
        "awaiting real tier": 0,
    }, payload


def test_unrowed_short_row_is_a_refusal_not_a_wrong_answer(tmp_path):
    """A row shorter than the `status` column index must refuse, not report the
    wrong count."""
    text = doc(TWO)
    anchor = row(TWO["1"][0]) + "\n"
    assert anchor in text, "fixture row anchor missing — arm is a no-op"
    short = "| F-001 | Some surface | views the panel |\n"
    text = text.replace(anchor, short, 1)
    assert short in text, "short row not substituted — arm is a no-op"
    rc, out, _ = run(write(tmp_path, text))
    assert rc == 2, f"a row shorter than its status column was mis-scored: {out}"
    assert "column" in out, out


def test_blank_table_line_is_refused_not_dropped(tmp_path):
    """`is_separator` filtered empty cells before `all()`, so an all-blank line
    satisfied all() over an EMPTY GENERATOR and vanished from both denominators —
    the exact silent skip the previous commit existed to close, reached by a line
    with no non-empty cell to trigger it."""
    text = doc(TWO)
    anchor = row(TWO["1"][0]) + "\n"
    blank = "|  |  |  |  |  |  |  |  |  |  |\n"
    text = text.replace(anchor, anchor + blank, 1)
    assert blank in text, "blank line not inserted — arm is a no-op"
    rc, out, _ = run(write(tmp_path, text))
    assert rc == 2, f"an all-blank table line was dropped from both denominators: {out}"
    assert "would be dropped from the census" in out, out


def test_section_table_without_status_column_is_refused(tmp_path):
    """A §3 table whose header lost `status` has nothing to tally; silently
    tallying zero statuses would print a table of zeros."""
    rc, out, _ = run(
        write(
            tmp_path,
            doc(TWO).replace(
                ROW_HEADER,
                "| id | surface | action | API calls | backend | state | evidence | modules | real tier | ruling | priority |",
                1,
            ),
        )
    )
    assert rc == 2, f"a §3 table with no `status` column was tallied anyway: {out}"
    assert "no `status` column" in out, out


def test_no_sections_at_all_is_refused(tmp_path):
    rc, out, _ = run(
        write(
            tmp_path,
            doc(TWO)
            .replace("### 3.1 Section 1", "### Section 1", 1)
            .replace("### 3.2 Section 2", "### Section 2", 1),
        )
    )
    assert rc == 2, f"a doc with no `### 3.x` heading passed: {out}"
    assert "no corpus" in out, out


def test_duplicate_column_name_in_a_header_is_refused(tmp_path):
    rc, out, _ = run(
        write(
            tmp_path,
            doc(TWO).replace(
                ROW_HEADER,
                ROW_HEADER.replace("| evidence |", "| evidence |", 1).replace(
                    "| modules |", "| evidence |", 1
                ),
                1,
            ),
        )
    )
    assert rc == 2, f"a header naming one column twice was resolved: {out}"
    assert "duplicate column name" in out, out


# --------------------------------------------- the mutants that must stay GREEN


def test_escaped_pipe_inside_a_cell_is_not_a_column(tmp_path):
    """The real F-006 carries `42% \\| 61°C` in its action cell. A parser that
    split on every pipe would invent a column, shift `status` right of it, and
    start reading prose as a status — visible here and nowhere else, because an
    ordinary doc scores correctly under the broken parser too."""
    one = {"1": [("F-001", "half-built", "shows `42% \\| 61°C` thresholds")]}
    rc, out, payload = run(write(tmp_path, doc(one)))
    assert rc == 0, f"an escaped pipe was read as a column break: {out}"
    assert payload["statuses"] == {
        "unverified": 0,
        "half-built": 1,
        "leftover": 0,
        "awaiting real tier": 0,
    }, payload


def test_a_later_section_may_own_its_own_id_table(tmp_path):
    """The last `### 3.x` section's corpus ends at the next `## `, not at EOF.

    It used to run to EOF, which today is harmless only because §4..§8 of the real
    inventory carry no `id` column — the tally stayed right while the slice held 7
    tables and 414 pipe lines. The cliff was one legitimate edit away: the moment a
    later section gained an `id`-headed table, the last section would raise
    "expected exactly 1 id-headed table". The bound is the fix; this arm is the
    control that proves it — the same doc reddens on the unbounded slice.
    """
    later = (
        "\n## 4. Not a feature section\n\n"
        + ROW_HEADER
        + "\n"
        + ROW_SEP
        + "\n"
        + row(("F-900", "leftover"))
        + "\n"
    )
    # Insert at the END of the LAST section's slice, so the `## 4.` table sits inside
    # the window the unbounded slice used to take (last `### 3.x` -> EOF) and outside
    # the bounded one (last `### 3.x` -> next `## `). Appending after the whole doc
    # would land in the same window again and prove nothing.
    anchor = row(TWO["2"][-1]) + "\n"
    text = doc(TWO)
    assert anchor in text, "anchor not in fixture doc — arm is a no-op"
    text = text.replace(anchor, anchor + later, 1)
    rc, out, payload = run(write(tmp_path, text))
    assert rc == 0, f"a table in a later `## ` section was pulled into §3's tally: {out}"
    # TWO carries 5 rows; the unbounded slice found TWO id-headed tables in §3.2 and
    # raised rc=2. If F-900 leaked into the tally instead, rows would read 6.
    assert payload["rows"] == 5, f"F-900 leaked into §3's tally: {payload}"
    assert payload["statuses"]["leftover"] == 1, payload
