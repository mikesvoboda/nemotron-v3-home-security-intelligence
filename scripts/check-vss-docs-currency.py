#!/usr/bin/env python3
"""Gate: a stale status claim in docs/vss-integration/ needs a dated correction above it.

The defect class. `docs/vss-integration/README.md` and `AGENTS.md` both asserted "nothing
implemented yet" six days after `4bfd6fa4` made the VLM path the shipped default
(the `PIPELINE_MODE` default in `docker-compose.prod.yml`), and nothing in CI could see it: `agents-md.yml` runs a
presence/reference validator, not a content one, and `scripts/docs-drift-rules.yml` carries no vss
rule. Three-plus meta-docs carried
one defect (README:6, AGENTS:6, 00-context.md:5, and the design spec's own Status line).

The rule. Where a doc makes a claim the code no longer supports, a **dated** blockquote naming that
claim must appear BEFORE it — a correction the reader meets after the lie corrects nothing. The
stale sentence itself stays: these are the research record, and rewriting frozen prose is out of
bounds (see `docs/vss-integration/AGENTS.md`). The form being enforced is the in-doc precedent at
`docs/vss-integration/06-repo-a-readiness.md:11`.

Two hazards the first version of this gate fell into, both pinned by tests:

- **A correction that quotes the sentence it retires** (`The line below ("Nothing is implemented
  yet.") is now false`) puts the claim inside the banner. Asked of the claim's first hit — which is
  then the banner's own line — "is a banner above it?" answers no, and a correctly written doc
  fails. So the claim's occurrences are searched from AFTER the last dated banner onward.
- **An unrelated dated banner** is not a correction of anything: `00-context.md:3` carries an
  Errata banner about other claims, and a gate that only asked "any dated banner above the line?"
  passed that file without it ever addressing its own status line. So a banner counts only if it
  names the claim — with whitespace collapsed, since the docs are wrapped prose and a quoted
  sentence breaks mid-phrase.

Beyond the three status claims, two further checks keep the folder trustworthy as the source of truth
for the AI/VLM stack (owner decision 2026-10-03). Both are ONLY activated by what is present, so a
tree without them is unaffected, and both read only files under docs/vss-integration plus the code files
a pin names. NOTHING here reads the design spec, the ledger or git history: those are absent from
mutmut's mutant home (pyproject.toml, the "tenth member" comment), and a unit test that path-reads an
absent docs/ tree aborts its coverage gather. A row that quotes the spec or ledger is skipped when
that file is absent.

1. Register consistency (17-action-plan.md). The header count, every Dashboard table cell, every
   area heading count and the P0/P1 list are RECOMPUTED from the `#### ISS-nnn` blocks and compared;
   duplicate ids fail (a lettered suffix such as ISS-088b is a distinct id), and so does a block filed
   outside section 5 (ISS-087 and ISS-088 were once filed under "Withdrawn"). A failure prints the
   recomputed counts, so nobody hand-counts.
2. The State page (README.md). Active when README carries `<!-- state-of-the-stack as-of=DATE
   verified-at=SHA -->`. Then: every numbered doc must be named in README (the document map);
   relative links that resolve inside the folder must exist; every ISS-, E- and OD- id README cites
   must be defined (an OD id preceded by `18/` is doc 18's own list and is not checked);
   `<!-- pin: FILE :: LITERAL -->` rows must still match the code; and `<!-- known-false: FILE ::
   QUOTE -->` rows expire loudly once the quoted text leaves FILE.

Usage: check-vss-docs-currency.py [REPO_ROOT]   (default: repo root inferred from this file)
Exit 0 clean; exit 1 with one line per offending file.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# (path relative to repo root, the claim that must be corrected, human-readable label)
# Verified against `main` 51f635e5 [V]. Kept deliberately narrow: exact phrases, so the gate
# cannot fail on prose that merely discusses the topic.
CLAIMS: list[tuple[str, str, str]] = [
    ("docs/vss-integration/README.md", "nothing implemented yet", "status line"),
    ("docs/vss-integration/AGENTS.md", "Nothing is implemented yet", "start-here line"),
    ("docs/vss-integration/00-context.md", "Research in progress", "status line"),
]

# A dated correction: a blockquote leading with a CORRECTION word and carrying a full ISO date.
# `Status` is deliberately NOT admitted. The stale line in README.md is itself a dated blockquote —
# "> **Status (2026-09-23): design approved, nothing implemented yet.**" — so a gate that accepted a
# Status banner would let the lie vouch for itself.
BANNER = re.compile(r"^>\s+\*\*(?:Currency|Retirement note|Errata)[^*]*\b20\d\d-\d\d-\d\d\b", re.I)

# Markdown decoration that must not break a phrase match: the blockquote marker (a banner's prose
# continues on each `>` line, and joined text with `>` stranded mid-sentence matches nothing), plus
# emphasis markers and code spans — banners quote the stale sentence with `**` around it.
_MARKUP = re.compile(r"(?m)[`*_]+|^>+")


def normalise(text: str) -> str:
    """A line as prose, for phrase matching across wrap and emphasis."""
    return re.sub(r"\s+", " ", _MARKUP.sub("", text)).strip()


def banner_blocks(lines: list[str]) -> list[range]:
    """Maximal runs of blockquote lines whose FIRST line is a dated correction.

    Block-level because a real banner wraps over several `>` lines and names the claim somewhere in
    the middle of it — matching line-by-line misses a correction whose quote falls on a later line.
    """
    blocks: list[range] = []
    i = 0
    while i < len(lines):
        if BANNER.match(lines[i]):
            j = i
            while j < len(lines) and lines[j].startswith(">"):
                j += 1
            blocks.append(range(i, j))
            i = j
        else:
            i += 1
    return blocks


def names_claim(block: range, lines: list[str], needle: str) -> bool:
    """Does this banner NAME the claim it is supposed to correct?

    Required, not merely "is there a dated banner above it": 00-context.md:3 carries an Errata
    banner about entirely other claims, and it satisfied an earlier version of this gate while
    its status line stood uncorrected. Matched against the whole block joined — these docs are
    prose-wrapped, so a quoted sentence routinely breaks mid-phrase.
    """
    # Joined with newlines, not spaces: the `^` in _MARKUP is what strips each line's blockquote
    # marker, and `^` only anchors after a newline.
    return needle in normalise("\n".join(lines[i] for i in block))


def check(root: Path) -> list[str]:
    problems: list[str] = []
    for rel, claim, label in CLAIMS:
        path = root / rel
        if not path.is_file():
            problems.append(f"{rel}: missing — the gate's own path moved; update CLAIMS")
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        needle = normalise(claim)
        blocks = banner_blocks(lines)
        in_banner = {i for b in blocks for i in b}

        # Where the stale claim stands on its own — outside any banner, since a correction quotes
        # the sentence it retires and that quote is not the claim standing.
        prose = {i: normalise(line) for i, line in enumerate(lines) if i not in in_banner}
        standalone = [i for i, text in prose.items() if needle in text]
        if not standalone:
            if any(needle in normalise(line) for line in lines):
                problems.append(
                    f"{rel} ({label}): {claim!r} now appears ONLY inside the dated banner — the "
                    f"banner replaced the stale line instead of preceding it; the original stays as the record"
                )
            continue  # claim retired outright: nothing to correct
        # A correction the reader meets after the lie corrects nothing, so the naming banner must
        # END before the claim's first standalone occurrence.
        first = standalone[0]
        if not any(b.stop <= first and names_claim(b, lines, needle) for b in blocks):
            problems.append(
                f"{rel}:{first + 1} ({label}) claims {claim!r} with no dated correction naming it "
                f"above — add one in the form of the Retirement note in docs/vss-integration/06-repo-a-readiness.md"
            )
    return problems


# ---- register consistency ---------------------------------------------------------------------
REGISTER_REL = "docs/vss-integration/17-action-plan.md"
README_REL = "docs/vss-integration/README.md"
FOLDER_REL = "docs/vss-integration"
ISS_HEADING = re.compile(r"^#### (ISS-\d+[a-z]?) — (.+)$")
ISS_META = re.compile(
    r"^`(P[0-3])`(?: \([^)]*\))? · `(\w+)` · actor `([\w-]+)` · status `([\w-]+)`"
)
AREA_HEADING = re.compile(r"^### (.+) \((\d+)\)\s*$")
P1_BULLET = re.compile(r"^- \*\*(ISS-\d+[a-z]?)\*\*")
HEADER_COUNT = re.compile(r"It holds (\d+) issues")
CLOSED = {"done", "wont-fix", "superseded"}
SEVERITIES = ("P0", "P1", "P2", "P3")


def parse_register(lines: list[str]) -> tuple[list[dict[str, str]], list[str]]:
    """Blocks in file order, each with its section and area, plus structural problems."""
    blocks: list[dict[str, str]] = []
    problems: list[str] = []
    section = area = ""
    for i, line in enumerate(lines):
        if line.startswith("## "):
            section, area = line, ""
        elif line.startswith("### ") and section.startswith("## 5."):
            m = AREA_HEADING.match(line)
            area = m.group(1) if m else ""
        m = ISS_HEADING.match(line)
        if not m:
            continue
        meta = next(
            (
                x
                for x in (ISS_META.match(lines[j]) for j in range(i + 1, min(i + 8, len(lines))))
                if x
            ),
            None,
        )
        if meta is None:
            problems.append(
                f"{REGISTER_REL}:{i + 1} {m.group(1)} has no metadata line (severity, kind, actor, status)"
            )
            continue
        if not section.startswith("## 5."):
            problems.append(
                f"{REGISTER_REL}:{i + 1} {m.group(1)} is filed under {section!r}, not section 5 (the register): "
                "intake rule 2 puts a block in its area section"
            )
        sev, kind, actor, status = meta.groups()
        blocks.append(
            {
                "id": m.group(1),
                "line": str(i + 1),
                "area": area,
                "sev": sev,
                "kind": kind,
                "actor": actor,
                "status": status,
            }
        )
    return blocks, problems


def _tables(lines: list[str], start: int, stop: int) -> dict[str, list[list[str]]]:
    """Markdown tables in lines[start:stop], keyed by their first header cell."""
    out: dict[str, list[list[str]]] = {}
    i = start
    while i < stop:
        if (
            lines[i].startswith("|")
            and i + 1 < stop
            and set(lines[i + 1].replace("|", "").strip()) <= set("- :")
        ):
            header = [c.strip() for c in lines[i].strip().strip("|").split("|")]
            rows: list[list[str]] = []
            j = i + 2
            while j < stop and lines[j].startswith("|"):
                rows.append([c.strip() for c in lines[j].strip().strip("|").split("|")])
                j += 1
            out[header[0]] = [header, *rows]
            i = j
        else:
            i += 1
    return out


def _count(blocks: list[dict[str, str]], key: str, *, only_open: bool) -> dict[str, int]:
    counts: dict[str, int] = {}
    for b in blocks:
        if only_open and b["status"] in CLOSED:
            continue
        counts[b[key]] = counts.get(b[key], 0) + 1
    return counts


def check_register(root: Path) -> list[str]:
    path = root / REGISTER_REL
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    blocks, problems = parse_register(lines)
    n = len(blocks)
    n_open = sum(1 for b in blocks if b["status"] not in CLOSED)

    seen: dict[str, str] = {}
    for b in blocks:
        if b["id"] in seen:
            problems.append(
                f"{REGISTER_REL}:{b['line']} duplicate id {b['id']} (first at line {seen[b['id']]}); a collision takes a lettered suffix, never a renumber"
            )
        seen.setdefault(b["id"], b["line"])

    head = " ".join(lines[:30])
    m = HEADER_COUNT.search(head)
    if m and int(m.group(1)) != n:
        problems.append(
            f"{REGISTER_REL}: the header says it holds {m.group(1)} issues, but {n} `#### ISS-` blocks exist"
        )

    # Dashboard tables, recomputed from the blocks.
    dash_at = next((i for i, x in enumerate(lines) if x.startswith("## 2.")), None)
    if dash_at is not None:
        end = next(
            (
                i
                for i in range(dash_at + 1, len(lines))
                if lines[i].startswith("### ") or lines[i].startswith("## ")
            ),
            len(lines),
        )
        tables = _tables(lines, dash_at, end)
        status_counts = _count(blocks, "status", only_open=False)
        want_status = {
            **dict.fromkeys(("open", "in-progress", "done", "wont-fix", "superseded"), 0),
            **status_counts,
            "total": n,
        }

        def compare(table: str, label: str, col: str, got: str, want: int) -> None:
            if not got.lstrip("-").isdigit() or int(got) != want:
                problems.append(
                    f"{REGISTER_REL}: Dashboard {table} table, row {label!r}, column {col}: says {got}, recomputed from the blocks {want}"
                )

        if "Status" in tables:
            rows = {r[0]: r for r in tables["Status"][1:]}
            for label, want in want_status.items():
                if label in rows:
                    compare("Status", label, "Count", rows[label][1], want)
            for label in status_counts:
                if label not in rows:
                    problems.append(
                        f"{REGISTER_REL}: Dashboard Status table has no row for status {label!r} ({status_counts[label]} blocks)"
                    )
        for table, key, labels in (
            ("Severity", "sev", SEVERITIES),
            ("Actor", "actor", None),
            ("Kind", "kind", None),
        ):
            if table not in tables:
                continue
            rows = {r[0]: r for r in tables[table][1:]}
            filed, opened = (
                _count(blocks, key, only_open=False),
                _count(blocks, key, only_open=True),
            )
            for label in set(filed) | set(labels or ()):
                if label not in rows:
                    problems.append(
                        f"{REGISTER_REL}: Dashboard {table} table has no row {label!r} ({filed.get(label, 0)} blocks)"
                    )
                    continue
                compare(table, label, "Filed", rows[label][1], filed.get(label, 0))
                compare(table, label, "Open", rows[label][2], opened.get(label, 0))
            if "total" in rows:
                compare(table, "total", "Filed", rows["total"][1], n)
                compare(table, "total", "Open", rows["total"][2], n_open)
        if "Area" in tables:
            rows = {r[0]: r for r in tables["Area"][1:]}
            for area in sorted({b["area"] for b in blocks}):
                mine = [b for b in blocks if b["area"] == area]
                if area not in rows:
                    problems.append(
                        f"{REGISTER_REL}: Dashboard Area table has no row {area!r} ({len(mine)} blocks)"
                    )
                    continue
                for col, want in (
                    *((sv, sum(1 for b in mine if b["sev"] == sv)) for sv in SEVERITIES),
                    ("Filed", len(mine)),
                    ("Open", sum(1 for b in mine if b["status"] not in CLOSED)),
                ):
                    idx = tables["Area"][0].index(col)
                    compare("Area", area, col, rows[area][idx], want)

    # Area headings in section 5 carry their own filed count.
    in5 = False
    for i, line in enumerate(lines):
        if line.startswith("## "):
            in5 = line.startswith("## 5.")
        elif in5 and line.startswith("### "):
            hm = AREA_HEADING.match(line)
            if hm:
                have = sum(1 for b in blocks if b["area"] == hm.group(1))
                if have != int(hm.group(2)):
                    problems.append(
                        f"{REGISTER_REL}:{i + 1} area heading {hm.group(1)!r} says ({hm.group(2)}), but {have} blocks sit under it"
                    )

    # The P0/P1 list names exactly the blocks filed P0 or P1.
    list_at = next((i for i, x in enumerate(lines) if x.startswith("### P0 and P1 issues")), None)
    if list_at is not None:
        stop = next(
            (i for i in range(list_at + 1, len(lines)) if lines[i].startswith("#")), len(lines)
        )
        listed = {pm.group(1) for x in lines[list_at:stop] if (pm := P1_BULLET.match(x))}
        want_ids = {b["id"] for b in blocks if b["sev"] in ("P0", "P1")}
        for missing in sorted(want_ids - listed):
            problems.append(
                f"{REGISTER_REL}: the P0 and P1 list omits {missing}, which is filed P0 or P1"
            )
        for extra in sorted(listed - want_ids):
            problems.append(
                f"{REGISTER_REL}: the P0 and P1 list names {extra}, which is not filed P0 or P1"
            )

    if problems:
        problems.append(
            f"{REGISTER_REL}: recomputed from {n} blocks (open {n_open}): "
            f"status {dict(sorted(_count(blocks, 'status', only_open=False).items()))}; "
            f"severity filed {dict(sorted(_count(blocks, 'sev', only_open=False).items()))}, "
            f"open {dict(sorted(_count(blocks, 'sev', only_open=True).items()))}; "
            f"actor filed {dict(sorted(_count(blocks, 'actor', only_open=False).items()))}, "
            f"open {dict(sorted(_count(blocks, 'actor', only_open=True).items()))}; "
            f"kind filed {dict(sorted(_count(blocks, 'kind', only_open=False).items()))}, "
            f"open {dict(sorted(_count(blocks, 'kind', only_open=True).items()))}"
        )
    return problems


# ---- the State page ---------------------------------------------------------------------------
STATE_MARKER = re.compile(r"<!--\s*state-of-the-stack\b(.*?)-->", re.S)
AS_OF = re.compile(r"as-of=(\d{4}-\d{2}-\d{2})\s+verified-at=([0-9a-f]{7,40})")
PIN = re.compile(r"<!--\s*pin:\s*(\S+)\s*::\s*(.+?)\s*-->")
KNOWN_FALSE = re.compile(r"<!--\s*known-false:\s*(\S+)\s*::\s*(.+?)\s*-->")
MD_LINK = re.compile(r"\]\(([^)\s]+)\)")
ISS_REF = re.compile(r"\bISS-\d+[a-z]?\b")
E_REF = re.compile(r"(?<![\w/-])E(\d{1,3})\b")
OD_REF = re.compile(r"(?<!18/)\bOD-\d+\b")
ERRATA_DEF = re.compile(r"(?m)^\*\*E(\d+)\.")
OD_DEF = re.compile(r"(?m)^\|\s*(OD-\d+)\s*\|")


def check_state_page(root: Path) -> list[str]:
    readme = root / README_REL
    if not readme.is_file():
        return []
    text = readme.read_text(encoding="utf-8")
    marker = STATE_MARKER.search(text)
    if marker is None:
        return []
    problems: list[str] = []
    if not AS_OF.search(marker.group(1)):
        problems.append(
            f"{README_REL}: the state-of-the-stack marker needs as-of=YYYY-MM-DD verified-at=<sha>"
        )

    folder = root / FOLDER_REL
    for doc in sorted(folder.glob("[0-9][0-9]-*.md")):
        if doc.name not in text:
            problems.append(f"{README_REL}: the document map does not name {doc.name}")

    for target in MD_LINK.findall(text):
        rel = target.split("#")[0]
        if not rel or re.match(r"^[a-z][a-z0-9+.-]*:", rel):
            continue
        resolved = (readme.parent / rel).resolve()
        try:
            resolved.relative_to(folder.resolve())
        except ValueError:
            continue  # leaves the folder: the spec, ledger and code are absent from mutmut's home
        if not resolved.exists():
            problems.append(f"{README_REL}: link target {rel} does not exist")

    # ids README cites must be defined where they are defined.
    register = root / REGISTER_REL
    reg_text = register.read_text(encoding="utf-8") if register.is_file() else ""
    iss_defined = {m.group(1) for line in reg_text.splitlines() if (m := ISS_HEADING.match(line))}
    od_defined = set(OD_DEF.findall(reg_text))
    e_defined: set[str] = set()
    for name in ("11-errata-2026-09-23.md", "16-errata-2026-10-03.md"):
        f = folder / name
        if f.is_file():
            e_defined |= set(ERRATA_DEF.findall(f.read_text(encoding="utf-8")))
    body = STATE_MARKER.sub("", PIN.sub("", KNOWN_FALSE.sub("", text)))
    for ref in sorted(set(ISS_REF.findall(body)) - iss_defined):
        problems.append(f"{README_REL}: cites {ref}, which is not a block in 17-action-plan.md")
    for ref in sorted(set(OD_REF.findall(body)) - od_defined):
        problems.append(
            f"{README_REL}: cites {ref}, which is not a row of 17's owner-decision table (doc 18's own ids are written 18/OD-n)"
        )
    for ref in sorted(set(E_REF.findall(body)) - e_defined, key=int):
        problems.append(f"{README_REL}: cites E{ref}, which neither errata doc defines")

    for rel, literal in PIN.findall(text):
        target = root / rel
        if not target.is_file():
            problems.append(f"{README_REL}: pin on {rel} but that file is missing")
        elif literal not in target.read_text(encoding="utf-8"):
            problems.append(
                f"{README_REL}: pin {literal!r} not found in {rel}: the page says it and the code no longer does; "
                "update the README (or the pin) to the code"
            )

    for rel, quote in KNOWN_FALSE.findall(text):
        target = root / rel
        if not target.is_file():
            continue  # spec and ledger are absent from the mutant home; never abort on that
        if normalise(quote) not in normalise(target.read_text(encoding="utf-8")):
            problems.append(
                f"{README_REL}: known-false row on {rel} has expired, the quoted text is gone: remove the row ({quote!r})"
            )
    return problems


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path(__file__).resolve().parent.parent
    problems = [*check(root), *check_register(root), *check_state_page(root)]
    if problems:
        print("VSS docs currency — FAIL")
        for p in problems:
            print(f"  {p}")
        return 1
    print("VSS docs currency — ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
