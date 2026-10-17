#!/usr/bin/env python3
"""Compute feature-inventory.md's §2 summary from the §3 rows it summarizes (ruling 251).

    uv run python scripts/check-inventory-summary-arith.py [PATH] [--json]

Prints §2's table -- per `### 3.x` section, its row count and each status's count, then
the `all` row -- from the rows themselves. §2 is not stored in the document any more:
until ruling 251 it was a hand-kept copy of these numbers, and two PRs that flipped
different rows both edited its `all` row, so they conflicted though their real edits
did not (about 20 recount and conflict commits across 11 PRs in two days). The
document's §2 now says how to print it.

Call it by path, the way its only automated caller does:
`scripts/test_check_inventory_summary_arith.py` runs
`sys.executable <this file> <doc> --json`, and CI runs that test
(`.github/workflows/ci.yml`, the collection-sanity test list). No CI step names this
file itself -- a `scripts/` path written in that step trips the entries pin.

`-m scripts.check-inventory-summary-arith` is not the form to advertise: it happens
to work from the repo root (no `scripts/__init__.py`, so it resolves as a namespace
package) and fails from any other cwd with ModuleNotFoundError.

Three parsing rules, each because the naive version manufactures a wrong answer:

  * cell split is ESCAPE-AWARE. `\\|` inside a cell is content, not a delimiter --
    F-006's action cell literally contains `42% \\| 61°C` -- so a bare `split("|")`
    invents a column and shifts every cell right of it, which lands on `status`.
  * columns are resolved by HEADER NAME, never by split index. A reordered table
    would otherwise tally the `evidence` column and still print plausible integers.
  * the STATUS VOCABULARY is the legend table under §1's `### Statuses`. A §3 row whose
    `status` is not in it is a failure, not an uncounted row: a new tier added to the
    rows without the legend is the silent half of a split.

Exit 0 with the table printed; 1 when a row carries a status outside the legend, or §2
stores a table again (ruling 251); 2 when the document cannot be scored -- a missing
legend, no `## 2.` heading, no `### 3.x` section, a section number used twice, a section
table with no `id` or `status` column, a duplicate `F-nnn`, a table line that is not a row. Every "found nothing" path exits
non-zero with its denominator printed, because an empty pass is the defect this
file exists to prevent. `inventory_witness.py` reuses the table helpers and
``check()``'s census.
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
H2_HEAD = re.compile(r"^## ")
SUMMARY_HEAD = re.compile(r"^## 2\. .*$", re.M)
STATUSES_HEAD = re.compile(r"^### Statuses\s*$", re.M)


class InventoryError(Exception):
    """The document is shaped in a way this checker cannot score. Always a failure."""


def split_row(line: str) -> list[str]:
    """Escape-aware Markdown row split: `\\|` survives, a bare `|` delimits."""
    guarded = line.strip().replace("\\|", ESCAPED_PIPE)
    return [c.replace(ESCAPED_PIPE, "|").strip() for c in guarded.strip().strip("|").split("|")]


def is_separator(cells: list[str]) -> bool:
    """A GFM table IS header + separator + rows: this line is what ADMITS a table."""
    # `if c` would let an ALL-BLANK line satisfy all() over an empty generator, so a
    # blanked-out table line vanished from both denominators instead of being refused.
    return bool(cells) and all(SEP_CELL.fullmatch(c) for c in cells)


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
    h2_heads = [i for i, ln in enumerate(lines) if H2_HEAD.match(ln)]
    if not heads:
        raise InventoryError("no '### 3.x' headings — the parser found no corpus to count")
    per_section: dict[str, dict[str, int]] = {}
    seen_ids: dict[str, str] = {}
    vocab: dict[str, int] = {}
    for n, start in enumerate(heads):
        num = SECTION_HEAD.match(lines[start]).group(1)
        if num in per_section:
            # Last copy would win: the first section's rows would vanish from the table
            # and the `all` row, with nothing left to compare the printed numbers to.
            raise InventoryError(f"section {num} appears twice -- the later copy would replace the earlier")
        # The section's corpus ends at the next `### 3.x` AND at the next `## ` — the
        # last section's next `### 3.x` does not exist, and an unbounded slice handed
        # §4..§8 (7 tables, 414 pipe lines) to this section's tally.
        bounds = [b for b in (heads[n + 1] if n + 1 < len(heads) else None,) if b is not None]
        bounds += [i for i in h2_heads if i > start]
        end = min(bounds) if bounds else len(lines)
        table = id_tables(lines[start:end], f"section {num}")[0]
        cols = header_columns(table)
        if "status" not in cols:
            raise InventoryError(f"section {num}: table header has no `status` column: {list(cols)}")
        status_i = cols["status"]
        tally: dict[str, int] = {}
        rows = 0
        unrowed: list[str] = []
        for line in table[1:]:
            cells = split_row(line)
            if is_separator(cells):
                continue
            if not ROW_ID.match(cells[0]):
                # NOT a silent skip. A row in an id table whose first cell is not an
                # `F-nnn` is either a malformed id or a prose line that got absorbed
                # into the table; counting it would invent a row, but SKIPPING it is
                # worse -- it drops one from the census in silence, and the printed
                # summary is wrong with nothing to compare it against. Measured on the
                # real document: 294 rows, 0 skipped, so this can only fire on content
                # that is already wrong.
                unrowed.append(cells[0][:40] or "<empty first cell>")
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
        if unrowed:
            shown = ", ".join(unrowed[:3])
            more = f" (+{len(unrowed) - 3} more)" if len(unrowed) > 3 else ""
            raise InventoryError(
                f"section {num}: {len(unrowed)} table line(s) are not `F-nnn` rows and would "
                f"be dropped from the census: {shown}{more}"
            )
        per_section[num] = {"rows": rows, **tally}
    return per_section, vocab


def legend_statuses(text: str) -> list[str]:
    """The status vocabulary, in order: the first column of the table under `### Statuses`."""
    match = STATUSES_HEAD.search(text)
    if not match:
        raise InventoryError("no '### Statuses' heading -- no legend to read the vocabulary from")
    body = text[match.end():]
    nxt = re.search(r"^#{1,6} ", body, re.M)
    body = body[: nxt.start()] if nxt else body
    found = [t for t in tables(body.splitlines()) if len(t) > 1 and is_separator(split_row(t[1]))]
    if len(found) != 1:
        raise InventoryError(f"'### Statuses': expected exactly 1 legend table, found {len(found)}")
    table = found[0]
    if "status" not in header_columns(table):
        raise InventoryError(f"'### Statuses' legend has no `status` column: {split_row(table[0])}")
    at = header_columns(table)["status"]
    vocabulary = [split_row(line)[at].strip("*` ") for line in table[2:]]
    if not vocabulary or not all(vocabulary):
        raise InventoryError(f"'### Statuses' legend names no status: {vocabulary}")
    return vocabulary


def section_titles(text: str) -> dict[str, str]:
    """`3.x` -> the heading's text after `### `, for the printed table's links."""
    return {
        m.group(1): line[4:].strip()
        for line in text.splitlines()
        if (m := SECTION_HEAD.match(line))
    }


def anchor(title: str) -> str:
    """GitHub's heading slug: lower case, punctuation dropped, spaces to hyphens."""
    return re.sub(r"[^\w\- ]", "", title.lower()).replace(" ", "-")


def stored_summary(text: str) -> bool:
    """Whether §2 holds a table again -- the hand-kept copy ruling 251 removed.

    The `## 2.` heading is required, whatever its title: ruling 251 keeps it so §3's numbers
    stay, and a guard that switched itself off when the heading moved would let the copy back.
    """
    match = SUMMARY_HEAD.search(text)
    if not match:
        raise InventoryError("no '## 2.' heading -- ruling 251 keeps it; the stored-table guard reads its body")
    body = text[match.end():].split("\n## ", maxsplit=1)[0]
    return any(len(t) > 1 and is_separator(split_row(t[1])) for t in tables(body.splitlines()))


def order(num: str) -> tuple[int, ...]:
    return tuple(int(x) for x in num.split("."))


def check(text: str) -> tuple[list[str], dict[str, object]]:
    """Return (problems, the census the printed table is built from)."""
    derived, vocab = derive_sections(text)
    vocabulary = legend_statuses(text)

    problems: list[str] = []
    unknown = sorted(s for s in vocab if s not in vocabulary)
    if unknown:
        problems.append(
            "status values in §3 rows are not in the '### Statuses' legend: "
            + ", ".join(f"{s!r} ({vocab[s]} rows)" for s in unknown)
        )
    if stored_summary(text):
        problems.append(
            "§2 stores a summary table again; ruling 251 computes it -- delete the table, "
            "this script prints it"
        )

    sections = {num: derived[num] for num in sorted(derived, key=order)}
    summed = {key: sum(s.get(key, 0) for s in sections.values()) for key in ("rows", *vocabulary)}
    census = {
        "sections_derived": len(sections),
        "rows": summed["rows"],
        "statuses": {s: summed[s] for s in vocabulary},
        "statuses_seen_in_rows": vocab,
        "sections": {num: {key: s.get(key, 0) for key in ("rows", *vocabulary)} for num, s in sections.items()},
    }
    return problems, census


def render(text: str, census: dict[str, object]) -> list[str]:
    """§2's table as Markdown: one row per section, then the `all` row."""
    titles = section_titles(text)
    statuses = list(census["statuses"])  # type: ignore[arg-type]
    out = [
        "| section | rows | " + " | ".join(statuses) + " |",
        "| --- | --- | " + " | ".join("---" for _ in statuses) + " |",
    ]
    for num, counts in census["sections"].items():  # type: ignore[union-attr]
        title = titles[num]
        cells = [str(counts["rows"])] + [str(counts[s]) for s in statuses]
        out.append(f"| [{title}](#{anchor(title)}) | " + " | ".join(cells) + " |")
    total = [str(census["rows"])] + [str(census["statuses"][s]) for s in statuses]  # type: ignore[index]
    out.append("| **all** | " + " | ".join(f"**{c}**" for c in total) + " |")
    return out


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
        problems, census = check(text)
    except InventoryError as exc:
        print(f"{args.path}: UNSCOREABLE — {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"path": str(args.path), "ok": not problems, **census, "problems": problems}, indent=2))
        return 1 if problems else 0

    print("\n".join(render(text, census)))
    for line in problems:
        print(f"{args.path.name}: {line}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
