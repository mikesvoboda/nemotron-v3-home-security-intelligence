#!/usr/bin/env python3
"""The plan fields ``lane_tick.py`` acts on, checked where they are written (ruling 197).

    uv run python scripts/uplevel/plan_lint.py [--root DIR]

Lane agents claim and act on what ``lane_tick.py`` parses out of the roster
(``docs/uplevel/roles/lane.md``), the package files (``docs/uplevel/packages/*.md``) and the ruling
map (``docs/uplevel/history/ruling-map.md``), and ``scripts/test_lane_tick.py`` pins that parsing on
fixtures only. So a plan edit could be read wrongly with every check green: ``[r196a]``'s first draft
wrapped ``**PR:** none`` / ``yet.`` across two lines, ``NONE_YET`` cannot span a newline, and the
package would have merged and never been offered. This lint reads the WORKING TREE (``--root``,
default this checkout) with lane_tick's own parsers -- imported, never re-implemented, so the two
cannot disagree about a field -- and fails when:

1. a roster queue token (as ``queue_entries`` reads the row) has no ``### `` block in that lane's
   package file -- ``next_claimable`` skips such a token silently, so the slot is never offered;
2. a block's ``**PR:**`` field (as ``PKG_FIELD`` captures it) is read by lane_tick as neither
   ``none yet`` (``next_claimable`` offers it) nor a ``#N`` (``held_claims`` holds it) -- the
   wrapped-"none yet" case;
3. one token is on two lanes' queues -- both agents would be offered the same claim;
4. a numbered-rulings row of the ruling map, from ruling 177 on, names no 10-digit record id.

Rows whose review label is ``none`` (coordinator, heavy-a, heavy-b, operator) are skipped, as the
digest gives them no package file to claim from. Exit 0 clean, 1 with one ``file:line: message``
line per finding; the last line always counts what was read, so an empty read cannot pass as clean.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coordinator_snapshot as snap  # sibling: agent_key, the lane of a roster row
import lane_tick as tick  # sibling: the parsers the digest acts on
from lane_tick import (
    BLOCK,
    NONE_YET,
    PKG_FIELD,
    PR_NUMBER,
    QUEUE_TOKEN,
    ROW,
    held_claims,
    next_claimable,
    queue_entries,
)

# The readers this lint shares with the digest; test_plan_lint pins each one as lane_tick's own
# object. QUEUE_TOKEN is reached through queue_entries, which reads a row's entries with it.
PARSERS = (ROW, queue_entries, QUEUE_TOKEN, BLOCK, PKG_FIELD, NONE_YET, PR_NUMBER, next_claimable, held_claims)  # fmt: skip

REPO_ROOT = Path(__file__).resolve().parents[2]
# lane_tick reads these from origin/main; the lint reads the same paths from the tree under review.
ROSTER_PATH = tick.ROSTER.partition(":")[2]
MAP_PATH = tick.MAP.partition(":")[2]
PKGS_PATH = tick.PKGS.partition(":")[2]  # docs/uplevel/packages/{}.md, keyed by the row's lane

# One package split by feature area across every lane (rulings 87, 175): its `### F2.3` block lives
# in frontend.md, and each lane's roster entry is that lane's BATCHES of it, claimed as `[F2.3]
# claim: <lane> golden UI batch` PRs -- not a package of the lane's own file. lane_tick's
# next_claimable skips it on the other lanes for that reason ("an F2.3 batch"). So it is held to
# its HOME file (a vanished F2.3 block still fails), and it is the one token allowed on several
# queues. A new shared package is a ruling, and a line here.
SHARED = {"F2.3": "frontend"}

RULINGS_HEADING = "## Rulings"
MAP_ROW = re.compile(r"^\|\s*(\d+)\s*\|")
RECORD_ID = re.compile(r"(?<!\d)\d{10}(?!\d)")
# Measured on main 2026-10-15: rows 1-145 and 147 carry no record id (they predate the record
# convention and are carried by PRs or by the 2026-10-12 design session); 146 and 148-195 all carry
# one. Ruling 177 introduced the digest's record filter, which finds a mapped record by ruling
# number OR comment id, so from 177 on a row without an id is a row the filter cannot match by id.
RECORD_IDS_FROM = 177


def blocks(text: str) -> list[tuple[str, int, str]]:
    """``(token, offset of the block, block text)`` per ``### `` block, split exactly as lane_tick
    splits (``text.split("### ")`` then ``BLOCK.match``); the offset gives a finding its line."""
    parts = text.split("### ")
    out, pos = [], len(parts[0])
    for part in parts[1:]:
        start = pos + len("### ")
        if m := BLOCK.match(part):
            out.append((m.group(1), start, part))
        pos = start + len(part)
    return out


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def roster_rows(text: str) -> list[dict]:
    """Every line ``ROW`` reads as a roster row -- the whole file, as ``identities`` scans it."""
    rows = []
    for n, line in enumerate(text.splitlines(), 1):
        if r := ROW.search(line):
            lane, _cell = snap.agent_key(r.group(1))
            rows.append({
                "line": n,
                "name": tick.footer_name(r.group(1)),
                "lane": lane,
                "label": r.group(3),
                "queue": queue_entries(r.group(2)),
            })  # fmt: skip
    return rows


def field_findings(path: str, text: str) -> list[str]:
    """Check 2: each ``**PR:**`` field, asked of lane_tick's own two readers of it."""
    out = []
    for token, start, block in blocks(text):
        field = PKG_FIELD.search(block)
        if field is None:
            continue  # a plan package with no PR field yet; lane_tick never offers it either
        one = "### " + block
        offered = next_claimable(one, [token], []) == token  # NONE_YET after .lstrip()
        named = PR_NUMBER.search(field.group(1))
        held = bool(named) and held_claims(one, [{"number": named.group(1), "title": ""}]) == [
            token
        ]
        if not (offered or held):
            value = snap.truncate(" ".join(field.group(1).split()), 50)
            out.append(
                f"{path}:{line_of(text, start + field.start())}: [{token}] **PR:** reads {value!r}: "
                "neither `none yet` on its own line nor a #N, so lane_tick never offers or holds it"
            )
    return out


def lint(root: Path) -> tuple[list[str], str]:
    """``(findings, what was read)`` for the plan files under ``root``. Read-only."""
    findings: list[str] = []

    def read(rel: str) -> str | None:
        try:
            return (root / rel).read_text(encoding="utf-8")
        except OSError as exc:
            findings.append(f"{rel}:1: unreadable: {exc.strerror or exc}")
            return None

    roster = read(ROSTER_PATH) or ""
    rows = roster_rows(roster)
    if not rows:
        findings.append(f"{ROSTER_PATH}:1: no roster row read (lane_tick's ROW matches none)")
    files: dict[str, str | None] = {}

    def package(lane: str) -> str | None:
        if lane not in files:
            files[lane] = read(PKGS_PATH.format(lane))
        return files[lane]

    first: dict[str, dict] = {}
    for row in rows:
        if row["label"] == "none":
            continue  # no review queue and no package file to claim from (lane_tick's NOTE arm)
        own = PKGS_PATH.format(row["lane"])
        text = package(row["lane"])
        tokens = {b[0] for b in blocks(text or "")}
        for token in dict.fromkeys(row["queue"]):  # a token twice in ONE queue is one slot
            home = SHARED.get(token)
            if home is not None:
                if token not in {b[0] for b in blocks(package(home) or "")}:
                    findings.append(
                        f"{ROSTER_PATH}:{row['line']}: {row['name']} queue token {token} is shared "
                        f"(rulings 87, 175) but {PKGS_PATH.format(home)} has no block for it"
                    )
                continue
            if text is not None and token not in tokens:
                findings.append(
                    f"{ROSTER_PATH}:{row['line']}: {row['name']} queue token {token} has no "
                    f"package block in {own}"
                )
            if token in first:
                findings.append(
                    f"{ROSTER_PATH}:{row['line']}: token {token} is on two lanes' queues: "
                    f"{first[token]['name']} (line {first[token]['line']}) and {row['name']}"
                )
            else:
                first[token] = row

    pkg_dir = root / Path(PKGS_PATH).parent
    pkg_files = sorted(pkg_dir.glob("*.md"))
    n_blocks = 0
    for f in pkg_files:
        rel = f.relative_to(root).as_posix()
        text = read(rel)
        if text is None:
            continue
        n_blocks += len(blocks(text))
        findings += field_findings(rel, text)
    if not n_blocks:
        findings.append(f"{Path(PKGS_PATH).parent}:1: no package block read")

    maptext = read(MAP_PATH) or ""
    in_rulings, n_rulings = False, 0
    for n, line in enumerate(maptext.splitlines(), 1):
        if line.startswith("## "):
            in_rulings = line.strip() == RULINGS_HEADING
            continue
        m = MAP_ROW.match(line) if in_rulings else None
        if not m:
            continue
        n_rulings += 1
        if int(m.group(1)) >= RECORD_IDS_FROM and not RECORD_ID.search(line):
            findings.append(f"{MAP_PATH}:{n}: ruling {m.group(1)}'s row names no record id")
    if not n_rulings:
        findings.append(f"{MAP_PATH}:1: no row read under {RULINGS_HEADING!r}")

    read_note = (
        f"read {len(rows)} roster rows, {len(pkg_files)} package files ({n_blocks} blocks), "
        f"{n_rulings} ruling-map rows"
    )
    return findings, read_note


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="scripts/uplevel/plan_lint.py",
        description="lint the plan fields lane_tick.py acts on (ruling 197)",
    )
    ap.add_argument("--root", type=Path, default=REPO_ROOT, help="checkout to read (default: this one)")  # fmt: skip
    a = ap.parse_args(argv)
    findings, read_note = lint(a.root)
    for f in findings:
        print(f)
    print(f"plan_lint: {len(findings)} finding(s); {read_note}")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
