#!/usr/bin/env python3
"""Re-derive feature-inventory.md's §2 summary table from the §3 rows it summarizes.

    uv run python -m scripts.check-inventory-summary-arith [PATH] [--json]

Section 2 publishes, per `### 3.x` section, a row count and a per-status count, plus
an `all` row. Until this checker existed NOTHING compared those numbers to the rows
they claim to count — `frontend/src/__tests__/feature-inventory.test.ts` holds ROWS
against code (routes, requests, cites, modules) and never opens the summary — so a
stale `half-built 152` merged green. Status edits are exactly what the R2 rulings
make constant, which makes this table the most-mutable arithmetic in `docs/`.

Three parsing rules, each because the naive version manufactures a wrong answer:

  * cell split is ESCAPE-AWARE. `\\|` inside a cell is content, not a delimiter —
    F-006's action cell literally contains `42% \\| 61°C` — so a bare `split("|")`
    invents a column and shifts every cell right of it, which lands on `status`.
  * columns are resolved by HEADER NAME, never by split index. A reordered table
    would otherwise tally the `evidence` column and still print plausible integers.
  * the summary table's own header declares the STATUS VOCABULARY. A §3 row whose
    `status` is not a summary column is an ERROR, not an uncounted row: a new tier
    added to the rows without a column is the silent half of a split.

Missing table, missing column, zero sections and a duplicate `F-nnn` are all
failures. An empty pass is the defect this file exists to prevent, so every
"found nothing" path exits 1 with its denominator printed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DOC = REPO_ROOT / "docs" / "reference" / "feature-inventory.md"

# A literal backslash-pipe, held out of the way while the row is split on real
# pipes. NUL cannot appear in a markdown file, so it cannot collide.
ESCAPED_PIPE = "\x00PIPE\x00"
ROW_ID = re.compile(r"^F-\d+$")
SECTION_HEAD = re.compile(r"^### (3\.\d+) ")
SEP_CELL = re.compile(r":?-{3,}:?")


class InventoryError(Exception):
    """The document is shaped in a way this checker cannot score. Always a failure."""


def split_row(line: str) -> list[str]:
    """Escape-aware Markdown row split: `\\|` survives, a bare `|` delimits."""
    guarded = line.strip().replace("\\|", ESCAPED_PIPE)
    return [c.replace(ESCAPED_PIPE, "|").strip() for c in guarded.strip().strip("|").split("|")]


def is_separator(cells: list[str]) -> bool:
    """A GFM table IS header + separator + rows: this line is what ADMITS a table."""
    return bool(cells) and all(SEP_CELL.fullmatch(c) for c in cells if c)


def tables(lines: list[str]) -> list[list[str]]:
    """Contiguous runs of pipe-delimited lines."""
    out: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if line.lstrip().startswith("|"):
            current.append(line)
        elif current:
            out.append(current)
            current = []
    if current:
        out.append(current)
    return out


def header_columns(table: list[str]) -> dict[str, int]:
    """Header name -> column index. Names are matched exactly, after backtick strip."""
    cells = split_row(table[0])
    cols = {c.strip("` ").lower(): i for i, c in enumerate(cells)}
    if len(cols) != len(cells):
        raise InventoryError(f"duplicate column name in table header: {cells}")
    return cols


def id_tables(body: list[str], where: str) -> list[list[str]]:
    """Tables in `body` whose header has an `id` column and a separator line."""
    found = []
    for table in tables(body):
        if len(table) < 2 or not is_separator(split_row(table[1])):
            continue
        if "id" not in header_columns(table):
            continue
        found.append(table)
    if len(found) != 1:
        raise InventoryError(f"{where}: expected exactly 1 id-headed table, found {len(found)}")
    return found


def derive_sections(text: str) -> tuple[dict[str, dict[str, int]], dict[str, int]]:
    """Walk `### 3.x` in order; tally rows and per-status counts from the real rows.

    Returns (per-section tallies, {vocabulary: how many rows carried it}).
    """
    lines = text.splitlines()
    heads = [i for i, ln in enumerate(lines) if SECTION_HEAD.match(ln)]
    if not heads:
        raise InventoryError("no '### 3.x' headings — the parser found no corpus to count")
    per_section: dict[str, dict[str, int]] = {}
    seen_ids: dict[str, str] = {}
    vocab: dict[str, int] = {}
    for n, start in enumerate(heads):
        num = SECTION_HEAD.match(lines[start]).group(1)
        end = heads[n + 1] if n + 1 < len(heads) else len(lines)
        table = id_tables(lines[start:end], f"section {num}")[0]
        cols = header_columns(table)
        if "status" not in cols:
            raise InventoryError(f"section {num}: table header has no `status` column: {list(cols)}")
        status_i = cols["status"]
        tally: dict[str, int] = {}
        rows = 0
        for line in table[1:]:
            cells = split_row(line)
            if is_separator(cells):
                continue
            if not ROW_ID.match(cells[0]):
                continue
            rows += 1
            row_id = cells[0]
            if row_id in seen_ids:
                raise InventoryError(
                    f"duplicate id {row_id}: sections {seen_ids[row_id]} and {num} both declare it"
                )
            seen_ids[row_id] = num
            if len(cells) <= status_i:
                raise InventoryError(
                    f"section {num} row {row_id}: {len(cells)} cells, `status` is column {status_i}"
                )
            status = cells[status_i]
            tally[status] = tally.get(status, 0) + 1
            vocab[status] = vocab.get(status, 0) + 1
        per_section[num] = {"rows": rows, **tally}
    return per_section, vocab


def parse_summary(text: str) -> tuple[dict[str, dict[str, int]], dict[str, int], list[str]]:
    """The published §2 table: (per-section rows, the `all` row, the status vocabulary)."""
    match = re.search(r"^## 2\. Summary\s*$", text, re.M)
    if not match:
        raise InventoryError("no '## 2. Summary' heading — nothing to check the rows against")
    body = text[match.end():].split("\n## ")[0]
    candidates = [t for t in tables(body.splitlines()) if len(t) > 2 and is_separator(split_row(t[1]))]
    if len(candidates) != 1:
        raise InventoryError(f"§2: expected exactly 1 summary table, found {len(candidates)}")
    table = candidates[0]
    cols = header_columns(table)
    for need in ("section", "rows"):
        if need not in cols:
            raise InventoryError(f"§2 summary header lacks `{need}`: {split_row(table[0])}")
    ordered = [c.strip("` ").lower() for c in split_row(table[0])]
    vocabulary = [c for c in ordered if c not in ("section", "rows")]
    if not vocabulary:
        raise InventoryError(f"§2 summary declares no status columns: {ordered}")

    per_section: dict[str, dict[str, int]] = {}
    all_row: dict[str, int] | None = None
    for line in table[1:]:
        cells = split_row(line)
        if is_separator(cells):
            continue
        first = cells[0].strip("* ").strip()
        label = first.split("]")[0].strip("[* ") if first.startswith("[") else first
        nums = re.match(r"^(3\.\d+)", label)
        target = None
        if nums:
            target = per_section.setdefault(nums.group(1), {})
        elif label.lower().strip("* ") == "all":
            target = all_row if all_row is not None else {}
        else:
            raise InventoryError(f"§2 summary row is neither a section nor `all`: {first!r}")
        try:
            target["rows"] = int(cells[cols["rows"]].strip("* "))
            for status in vocabulary:
                target[status] = int(cells[cols[status]].strip("* "))
        except (KeyError, ValueError) as exc:
            raise InventoryError(f"§2 summary row {first!r}: unreadable cell: {exc}") from exc
        if not nums and all_row is None:
            all_row = target
    if all_row is None:
        raise InventoryError("§2 summary has no `all` row to check the column sums against")
    return per_section, all_row, vocabulary


def check(text: str) -> tuple[list[str], dict[str, object]]:
    """Return (drift lines, a census of what was actually counted)."""
    derived, vocab = derive_sections(text)
    published, all_row, vocabulary = parse_summary(text)

    drift: list[str] = []
    unknown = sorted(s for s in vocab if s not in vocabulary)
    if unknown:
        drift.append(
            "status values in §3 rows are not columns of the §2 summary: "
            + ", ".join(f"{s!r} ({vocab[s]} rows)" for s in unknown)
        )
    missing_rows = sorted(set(published) - set(derived))
    extra_rows = sorted(set(derived) - set(published))
    if missing_rows:
        drift.append("§2 lists sections with no §3 table: " + ", ".join(missing_rows))
    if extra_rows:
        drift.append("§3 has sections the §2 summary never lists: " + ", ".join(extra_rows))

    def order(num: str) -> tuple[int, int]:
        return tuple(int(x) for x in num.split("."))  # type: ignore[return-value]

    for num in sorted(set(published) & set(derived), key=order):
        for key in ("rows", *vocabulary):
            want = published[num].get(key, 0)
            got = derived[num].get(key, 0)
            if want != got:
                drift.append(f"§3.{num[2:]} {key}: published {want}, derived from rows {got}")

    summed = {key: sum(derived[n].get(key, 0) for n in derived) for key in ("rows", *vocabulary)}
    for key in ("rows", *vocabulary):
        if all_row.get(key, 0) != summed[key]:
            drift.append(f"all {key}: published {all_row.get(key, 0)}, column sum {summed[key]}")

    census = {
        "sections_derived": len(derived),
        "sections_published": len(published),
        "rows": summed["rows"],
        "statuses": {s: summed[s] for s in vocabulary},
        "statuses_seen_in_rows": vocab,
        "drift_cells": len(drift),
    }
    return drift, census


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_DOC)
    parser.add_argument("--json", action="store_true", help="emit the census as JSON")
    args = parser.parse_args(argv)
    try:
        text = args.path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"{args.path}: cannot read: {exc}", file=sys.stderr)
        return 2
    try:
        drift, census = check(text)
    except InventoryError as exc:
        print(f"{args.path}: UNSCOREABLE — {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"path": str(args.path), "ok": not drift, **census, "drift": drift}, indent=2))
        return 1 if drift else 0

    print(
        f"{args.path.name}: sections={census['sections_derived']} rows={census['rows']} "
        + " ".join(f"{s}={n}" for s, n in census["statuses"].items())
    )
    if drift:
        print(f"DRIFT — {len(drift)} cell(s) disagree with the rows:")
        for line in drift:
            print(f"  {line}")
        return 1
    print("summary table agrees with the rows it summarizes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
