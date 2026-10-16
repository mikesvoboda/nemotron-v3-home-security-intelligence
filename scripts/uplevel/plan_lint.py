#!/usr/bin/env python3
"""The plan fields ``lane_tick.py`` acts on, checked where they are written (ruling 197).

    uv run python scripts/uplevel/plan_lint.py [--root DIR] [--baseline REF]

Lane agents claim and act on what ``lane_tick.py`` parses out of the roster
(``docs/uplevel/roles/lane.md``), the package files (``docs/uplevel/packages/*.md``) and the ruling
map (``docs/uplevel/history/ruling-map.md``), and ``scripts/test_lane_tick.py`` pins that parsing on
fixtures only. So a plan edit could be read wrongly with every check green: ``[r196a]``'s first draft
wrapped ``**PR:** none`` / ``yet.`` across two lines, ``NONE_YET`` cannot span a newline, and the
package would have merged and never been offered. This lint reads the WORKING TREE (``--root``,
default this checkout) with lane_tick's own parsers -- imported, never re-implemented, so the two
cannot disagree about a field -- and fails when:

1. a roster queue token (as ``queue_entries`` reads the row) has no ``### `` block in that lane's
   package file -- ``next_claimable`` skips such a token silently, so the slot is never offered.
   A row whose lane has no package file (heavy-a, the operator) is offered nothing by the digest;
   its tokens are assigned by the coordinator (UR-59) or run (UR-15) from blocks in any lane's
   file, so they are looked up across every package file (ruling 242);
2. a block's ``**PR:**`` field (as ``PKG_FIELD`` captures it) is neither ``none yet`` on one line
   (what ``next_claimable`` offers) nor a LEADING ``#N`` (what ``held_claims`` holds), or carries a
   ``none`` that ``NONE_YET`` does not read -- the wrapped ``none`` / ``yet.`` case, even when a
   later ``(issue #7102)`` would otherwise read as a held PR number;
3. one token is on two lanes' queues -- both agents would be offered (or assigned) the same claim.
   The operator's row is not a claim queue: it names real-tier RUNS of other lanes' packages
   (UR-15, ruling 188), so it is the one row this check does not count;
4. a numbered-rulings row of the ruling map names no 10-digit record id, other than the rows that
   predate record ids (1-145 and 147).

Every roster row is checked, whatever its review label. Until ruling 242 a ``none`` label skipped
the row, standing in for "no package file to claim from"; ruling 198 then set every row's label to
``none``, and checks 1 and 3 silently checked nothing. The lanes with no package file are now named
(``UNPACKAGED``).

``--baseline REF`` reads the same files at a git ref (``git show REF:<path>``) and fails only on
findings that ref lacks -- CI passes the PR merge commit's first parent (the ``main`` it merged
into), so a plan defect already on ``main`` reds ``main``'s own run and not every PR opened after it. A finding is matched by file and message, not
line, so an edit above it cannot make an old defect read as new. Without ``--baseline`` every
finding counts (a push to ``main``).

Exit 0 clean, 1 with one ``file:line: message`` line per (new) finding, 2 when the baseline ref
cannot be read. The last line always counts what was read, so an empty read cannot pass as clean.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coordinator_snapshot as snap  # sibling: agent_key, the runner, its error type
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
# object. QUEUE_TOKEN is reached through queue_entries, PR_NUMBER through held_claims.
PARSERS = (ROW, queue_entries, QUEUE_TOKEN, BLOCK, PKG_FIELD, NONE_YET, PR_NUMBER, next_claimable, held_claims)  # fmt: skip

REPO_ROOT = Path(__file__).resolve().parents[2]
# lane_tick reads these from origin/main; the lint reads the same paths from the tree under review.
ROSTER_PATH = tick.ROSTER.partition(":")[2]
MAP_PATH = tick.MAP.partition(":")[2]
PKGS_PATH = tick.PKGS.partition(":")[2]  # docs/uplevel/packages/{}.md, keyed by the row's lane
PKGS_DIR = PKGS_PATH.rpartition("/")[0]

# One package split by feature area across every lane (rulings 87, 175): its `### F2.3` block lives
# in frontend.md, and each lane's roster entry is that lane's BATCHES of it, claimed as `[F2.3]
# claim: <lane> golden UI batch` PRs -- not a package of the lane's own file. lane_tick's
# next_claimable skips it on the other lanes for that reason ("an F2.3 batch"). So it is held to
# its HOME file (a vanished F2.3 block still fails), and it is the one token allowed on several
# queues. A new shared package is a ruling, and a line here.
SHARED = {"F2.3": "frontend"}

# The lanes whose roster row lists real-tier RUNS of other lanes' packages, not claims (UR-15; the
# operator runs `O2.5` that ops-a builds, ruling 188). Check 3 does not count these rows; check 1
# still does, so a run of a package that has no block anywhere is a finding.
RUNS = frozenset({"operator"})

# The lanes with no package file of their own -- lane_tick's ``packages`` docstring: "the roster's
# coordinator, heavy-a, heavy-b and operator rows have work that is never packaged". Named, not
# inferred from which files exist, so a deleted ``docs.md`` stays an unreadable-file finding and a
# new lane cannot join this set by having no file. Until ruling 242 a ``none`` review label stood
# in for this set; ruling 198 made every label ``none``.
UNPACKAGED = frozenset({"coordinator", "heavy", "operator"})

# A held field LEADS with its PR number. `held_claims` reads the first `#N` anywhere, so a wrapped
# `**PR:** none` / `yet. (ruling 172; issue #7102)` reads to it as held by #7102 -- an issue.
LEADING_PR = re.compile(r"#(\d+)")
NONE_WORD = re.compile(r"\bnone\b", re.IGNORECASE)

RULINGS_HEADING = "## Rulings"
MAP_ROW = re.compile(r"^\|\s*(\d+)\s*\|")
RECORD_ID = re.compile(r"(?<!\d)\d{10}(?!\d)")
# Measured on main 2026-10-15: rows 1-145 and 147 carry no record id -- they predate the record
# convention and are carried by PRs or by the 2026-10-12 design session (147). Every other row, 146
# and 148 on, carries one, so the check covers all of them and exempts exactly these. Ruling 177's
# record filter finds a mapped record by ruling number OR comment id; a row without the id is one
# the filter can match only by number.
NO_RECORD_ID = frozenset(range(1, 146)) | {147}

Runner = Callable[[Sequence[str]], str]


class Finding(NamedTuple):
    path: str
    line: int
    message: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.message}"


class Disk:
    """The plan files of a checkout on disk."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def __str__(self) -> str:
        return str(self.root)

    def read(self, rel: str) -> str:
        return (self.root / rel).read_text(encoding="utf-8")

    def packages(self) -> list[str]:
        return sorted(p.relative_to(self.root).as_posix() for p in (self.root / PKGS_DIR).glob("*.md"))  # fmt: skip


class Ref:
    """The same files at a git ref, read with ``git show`` through the runner (no checkout)."""

    def __init__(self, run: Runner, root: Path, ref: str) -> None:
        self.run, self.root, self.ref = run, root, ref

    def __str__(self) -> str:
        return self.ref

    def git(self, *args: str) -> str:
        return self.run(["git", "-C", str(self.root), *args])

    def read(self, rel: str) -> str:
        return self.git("show", f"{self.ref}:{rel}")

    def packages(self) -> list[str]:
        listed = self.git("ls-tree", "--name-only", self.ref, "--", f"{PKGS_DIR}/")
        return sorted(p for p in listed.split() if p.endswith(".md"))


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


def field_findings(path: str, text: str) -> list[Finding]:
    """Check 2: each ``**PR:**`` field, asked of lane_tick's own two readers of it, held to the
    stricter shape: an offer is ``next_claimable``'s (``NONE_YET`` on the field's first line), a
    hold is ``held_claims``' AND a leading ``#N``, and a ``none`` NONE_YET does not read is a
    finding whatever else the field says."""
    out = []
    for token, start, block in blocks(text):
        field = PKG_FIELD.search(block)
        if field is None:
            continue  # a plan package with no PR field yet; lane_tick never offers it either
        value = field.group(1).lstrip()
        one = "### " + block
        offered = next_claimable(one, [token], []) == token
        lead = LEADING_PR.match(value)
        held = bool(lead) and held_claims(one, [{"number": lead.group(1), "title": ""}]) == [token]
        stray_none = bool(NONE_WORD.search(value)) and not NONE_YET.search(value)
        if not (offered or held) or stray_none:
            shown = snap.truncate(" ".join(value.split()), 50)
            out.append(
                Finding(
                    path,
                    line_of(text, start + field.start()),
                    f"[{token}] **PR:** reads {shown!r}: lane_tick offers only `none yet` on one "
                    "line and holds only a leading #N",
                )
            )
    return out


def lint(src: Disk | Ref) -> tuple[list[Finding], str]:
    """``(findings, what was read)`` for the plan files of ``src``. Read-only."""
    findings: list[Finding] = []

    texts: dict[str, str | None] = {}

    def read(rel: str) -> str | None:
        # Once per file: a package file is read for its lane's row, for the cross-file lookup and
        # for check 2, and an unreadable one is one finding, not three.
        if rel not in texts:
            try:
                texts[rel] = src.read(rel)
            except (OSError, snap.CommandError) as exc:
                findings.append(Finding(rel, 1, f"unreadable: {getattr(exc, 'strerror', None) or exc}"))  # fmt: skip
                texts[rel] = None
        return texts[rel]

    rows = roster_rows(read(ROSTER_PATH) or "")
    if not rows:
        findings.append(Finding(ROSTER_PATH, 1, "no roster row read (lane_tick's ROW matches none)"))  # fmt: skip
    try:
        pkg_files = src.packages()
    except (OSError, snap.CommandError) as exc:
        findings.append(Finding(PKGS_DIR, 1, f"unlisted: {exc}"))
        pkg_files = []
    files: dict[str, str | None] = {}

    def package(lane: str) -> str | None:
        if lane not in files:
            files[lane] = read(PKGS_PATH.format(lane))
        return files[lane]

    # Every block in every package file: what a row with no file of its own is looked up in.
    anywhere = {b[0] for rel in pkg_files for b in blocks(read(rel) or "")}
    first: dict[str, dict] = {}
    for row in rows:
        own = PKGS_PATH.format(row["lane"])
        if row["lane"] not in UNPACKAGED:
            # The digest reads ONLY this file (lane_tick's packages(lane)), so only it counts.
            text, where = package(row["lane"]), own
            tokens = {b[0] for b in blocks(text or "")}
        else:
            # No file of its own: never offered by a digest, assigned (UR-59) or run (UR-15).
            text, where, tokens = "", f"{PKGS_DIR}/*.md", anywhere
        at = (ROSTER_PATH, row["line"])
        for token in dict.fromkeys(row["queue"]):  # a token twice in ONE queue is one slot
            home = SHARED.get(token)
            if home is not None:
                if token not in {b[0] for b in blocks(package(home) or "")}:
                    findings.append(Finding(*at, f"{row['name']} queue token {token} is shared (rulings 87, 175) but {PKGS_PATH.format(home)} has no block for it"))  # fmt: skip
                continue
            if text is not None and token not in tokens:
                findings.append(Finding(*at, f"{row['name']} queue token {token} has no package block in {where}"))  # fmt: skip
            if row["lane"] in RUNS:
                continue  # a run of another lane's package, not a claim on it
            if token in first:
                # No line number in the MESSAGE: the baseline matches findings by message, and the
                # location already carries this row's line.
                findings.append(Finding(*at, f"token {token} is on two lanes' queues: {first[token]['name']} and {row['name']}"))  # fmt: skip
            else:
                first[token] = row

    n_blocks = 0
    for rel in pkg_files:
        text = read(rel)
        if text is None:
            continue
        n_blocks += len(blocks(text))
        findings += field_findings(rel, text)
    if not n_blocks:
        findings.append(Finding(PKGS_DIR, 1, "no package block read"))

    in_rulings, n_rulings = False, 0
    for n, line in enumerate((read(MAP_PATH) or "").splitlines(), 1):
        if line.startswith("## "):
            in_rulings = line.strip() == RULINGS_HEADING
            continue
        m = MAP_ROW.match(line) if in_rulings else None
        if not m:
            continue
        n_rulings += 1
        if int(m.group(1)) not in NO_RECORD_ID and not RECORD_ID.search(line):
            findings.append(Finding(MAP_PATH, n, f"ruling {m.group(1)}'s row names no record id"))
    if not n_rulings:
        findings.append(Finding(MAP_PATH, 1, f"no row read under {RULINGS_HEADING!r}"))

    read_note = (
        f"read {len(rows)} roster rows, {len(pkg_files)} package files ({n_blocks} blocks), "
        f"{n_rulings} ruling-map rows"
    )
    return findings, read_note


def over_baseline(head: list[Finding], base: list[Finding]) -> tuple[list[Finding], list[Finding]]:
    """``(new, already)``: the head's findings the base lacks, and the ones it already had.

    Matched by ``(file, message)`` -- never by line, which any edit above a finding moves -- and
    counted, so a second copy of an old defect is still a new finding.
    """
    left = Counter((f.path, f.message) for f in base)
    new, already = [], []
    for f in head:
        key = (f.path, f.message)
        if left[key]:
            left[key] -= 1
            already.append(f)
        else:
            new.append(f)
    return new, already


def main(argv: Sequence[str] | None = None, run: Runner = snap.run_command) -> int:
    ap = argparse.ArgumentParser(
        prog="scripts/uplevel/plan_lint.py",
        description="lint the plan fields lane_tick.py acts on (ruling 197)",
    )
    ap.add_argument("--root", type=Path, default=REPO_ROOT, help="checkout to read (default: this one)")  # fmt: skip
    ap.add_argument("--baseline", metavar="REF", help="fail only on findings REF's files lack (CI: the merge's first parent)")  # fmt: skip
    a = ap.parse_args(argv)
    findings, read_note = lint(Disk(a.root))
    if a.baseline is None:
        for f in findings:
            print(f)
        print(f"plan_lint: {len(findings)} finding(s); {read_note}")
        return 1 if findings else 0
    base = Ref(run, a.root, a.baseline)
    try:
        base.git("rev-parse", "--verify", "--quiet", f"{a.baseline}^{{commit}}")
    except snap.CommandError as exc:
        print(f"plan_lint: baseline {a.baseline} is unreadable ({exc}); nothing judged", file=sys.stderr)  # fmt: skip
        return 2
    base_findings, _ = lint(base)
    new, already = over_baseline(findings, base_findings)
    for f in new:
        print(f)
    for f in already:
        print(f"(already on {a.baseline}) {f}")
    print(f"plan_lint: {len(new)} new finding(s) over {a.baseline}, {len(already)} already there; {read_note}")  # fmt: skip
    return 1 if new else 0


if __name__ == "__main__":
    raise SystemExit(main())
