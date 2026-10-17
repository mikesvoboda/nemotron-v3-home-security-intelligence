#!/usr/bin/env python3
"""Grounds sweep over docs/reference/feature-inventory.md — the r231/r231b instrument.

    uv run python scripts/uplevel/grounds_sweep.py [--root REPO] [--inventory PATH]

The inventory's §1 exclusion prose carries the rows it does not list; every full-path
`file.py:NNN` coordinate INSIDE that exclusion region is a "ground" — a placed line that a §3
row may cite. A §3 row that cites a ground the exclusion prose never names is an UNNAMED citer:
the coordinate is doing placement work nothing above it admits. This script counts grounds and
unnamed citers and prints the controls that keep both counts honest. It is the instrument behind
`[r231b]`'s second Done-when clause ("grounds re-run reads 31 grounds, 0 unnamed with controls
green") and was committed at `[r231b]`'s review — the same figures had previously been printed
only from a /tmp copy, which contract rule 3 (rules.md "Tools live in the repo") refuses as
evidence (precedent: O1.7, docs/uplevel/history/packages-done.md, "scans nobody committed").

What the sweep binds, deliberately:

* **Region rule.** Grounds are the full-path coordinates from the line containing
  "Not listed, with the reason." to the `## 2.` heading — the exclusion prose ONLY. §1's intro
  and the §1 membership evidence above it also carry full-path cites and are NOT grounds (that
  was r231's frame; the region re-resolves by rule when lines are added upstream, so line
  numbers are printed, never assumed).
* **Shorthand.** A bare ``:NNN`` token binds to the last full path in the SAME code-span stream
  (the same cell, joined) — grounds and §3 rows both honor it, so a row citing ``:452`` after
  ``household_matcher.py:452`` is counted at the resolved pair, and the shorthand token count is
  printed so a drop in the total is visible, not silent.
* **Match granularity.** A coordinate with a range (`file.py:10-14`) keys on its START line at
  both ends; identity is `file.py:START`.
* **Controls.** Five coordinates with known-good verdicts print every run (one TRUE ground with
  its one citer, four non-grounds with their §3 citers). A parser that stops parsing prints the
  controls wrong before it prints a comfortable 31/0 — compare them against the values the
  block records rather than admiring the headline.

Exit codes: 0 = printed a full sweep (unnamed citers are REPORTED, not exited on — the reader
judges); 2 = the input could not be read or a structural anchor (`## 1.` / `## 2.` / the
exclusion line / `## 3.` / `## 4.`) is missing, naming what was missing (a silent skip turns a
census into a fossil).

This instrument is HAND-RUN: it is not wired into ci.yml, and neither is its output — docs/uplevel
and docs/reference sit outside the citation gate's five scoped dirs (ci.yml). Precedent for a
committed hand-run instrument: scripts/uplevel/r193-mutation-campaign.py.
"""

import argparse
import re
import sys
from pathlib import Path

CONTROL_KEYS = (
    "backend/services/alpr_service.py:559",
    "backend/api/routes/system.py:915",
    "backend/api/routes/system.py:1112",
    "backend/api/routes/system.py:1251",
    "scripts/feature_check.py:87",
)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=".", help="repo root (default: cwd)")
    ap.add_argument(
        "--inventory",
        default="docs/reference/feature-inventory.md",
        help="inventory path relative to --root (absolute paths pass through)",
    )
    return ap.parse_args()


def fail(msg):
    """Refuse loudly: name what failed, exit 2 (an exit CODE, not sys.exit(str)'s implicit 1)."""
    print(msg, file=sys.stderr)
    sys.exit(2)


def anchor(lines, start, end, needle, name):
    """Index of the line in [start,end) containing needle, or exit 2 naming the anchor."""
    for i in range(start, end):
        if needle in lines[i]:
            return i
    fail(f"grounds_sweep: anchor missing: {name} ({needle!r} between lines {start+1}-{end})")


def coords(blob):
    """Coordinate pairs a blob's code spans carry; a bare `:NNN` binds the last full path seen."""
    out = []
    last = None
    for m in re.finditer(r"`([^`]*)`", blob):
        t = m.group(1)
        fm = re.search(r"([\w./\-]+\.(?:py|tsx|ts|yml)):(\d+)", t)
        if fm:
            out.append(f"{fm.group(1)}:{fm.group(2)}")
            last = fm.group(1)
            continue
        sm = re.fullmatch(r":(\d+)", t.strip())
        if sm and last:
            out.append(f"{last}:{sm.group(1)}")
    return set(out)


def main() -> int:
    args = parse_args()
    path = Path(args.inventory)
    if not path.is_absolute():
        path = Path(args.root) / path
    try:
        lines = path.read_text().split("\n")
    except OSError as e:
        fail(f"grounds_sweep: cannot read {path}: {e}")

    print(f"grounds sweep over {path}")
    s1 = next((i for i, l in enumerate(lines) if l.startswith("## 1.")), None)
    if s1 is None:
        fail("grounds_sweep: anchor missing: '## 1.' heading")
    s2 = next((i for i, l in enumerate(lines) if l.startswith("## 2.")), None)
    if s2 is None or s2 <= s1:
        fail("grounds_sweep: anchor missing: '## 2.' heading after '## 1.'")
    gstart = anchor(lines, s1, s2, "Not listed, with the reason", "exclusion line")
    region = "\n".join(lines[gstart:s2])
    print("exclusion region: lines", gstart + 1, "to", s2, "(", s2 - gstart, "lines )")

    grounds = sorted(set(re.findall(r"`([\w./\-]+\.(?:py|tsx|ts|yml):\d+)`", region)))
    shorth = re.findall(r"`(:\d+)`", region)
    print("full-path grounds:", len(grounds), " shorthand tokens:", len(shorth))

    named = set(re.findall(r"\bF-\d{3}\b", "\n".join(lines[s1:s2])))

    s3 = next((i for i, l in enumerate(lines) if l.startswith("## 3.")), None)
    if s3 is None or s3 <= s2:
        fail("grounds_sweep: anchor missing: '## 3.' heading")
    s4 = next((i for i, l in enumerate(lines) if l.startswith("## 4.")), None)
    if s4 is None or s4 <= s3:
        fail("grounds_sweep: anchor missing: '## 4.' heading")

    rows = {}
    for i in range(s3, s4):
        if not lines[i].startswith("| F-"):
            continue
        c = [x.strip() for x in lines[i].split(" | ")]
        fid = c[0].strip("|").strip()
        if not re.fullmatch(r"F-\d{3}", fid):
            continue
        rows[fid] = coords(" ".join(c[3:7]))

    bad = []
    for g in grounds:
        for f in sorted(rows):
            if g in rows[f] and f not in named:
                bad.append((g, f))
    print("UNNAMED citers over true grounds:", len(bad))
    for b in sorted(set(bad)):
        print("   ", b)

    print("\n-- controls --")
    for g in CONTROL_KEYS:
        cit = sorted(f for f in rows if g in rows[f])
        print(f"  {g:46s} ground={g in grounds!s:5s} citers={cit}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
