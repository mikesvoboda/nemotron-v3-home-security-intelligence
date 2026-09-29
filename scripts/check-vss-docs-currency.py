#!/usr/bin/env python3
"""Gate: a stale status claim in docs/vss-integration/ needs a dated correction above it.

The defect class. `docs/vss-integration/README.md` and `AGENTS.md` both asserted "nothing
implemented yet" six days after `4bfd6fa4` made the VLM path the shipped default
(`docker-compose.prod.yml:578`), and nothing in CI could see it: `agents-md.yml` runs a
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
                f"above — add one in the form of docs/vss-integration/06-repo-a-readiness.md:11"
            )
    return problems


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path(__file__).resolve().parent.parent
    problems = check(root)
    if problems:
        print("VSS docs currency — FAIL")
        for p in problems:
            print(f"  {p}")
        return 1
    print("VSS docs currency — ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
