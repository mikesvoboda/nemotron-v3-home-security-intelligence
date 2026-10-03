#!/usr/bin/env python3
"""Print the next free id for the VSS register (ISS-nnn) or the errata (E<n>).

Why this exists. `docs/vss-integration/17-action-plan.md` allocated ids as "the highest ISS-nnn in the
register, plus one", read from ONE branch. ISS-088 was minted on a PR branch while the append-only
ledger already cited it, so two branches could mint the same id and nothing could renumber the loser
(the ledger cannot be edited). This script scans EVERY branch and remote ref, every worktree
(including uncommitted files), and the ledger and specs as well as the register, so an id cited
anywhere is taken. It cannot see another machine: the duplicate-id check in
scripts/check-vss-docs-currency.py is the backstop, and a collision takes a lettered suffix
(`--suffix-of ISS-088` prints ISS-088b), never a renumber.

Usage: vss-next-id.py [--repo PATH] iss|e [--where] [--suffix-of ISS-nnn]
  iss             next free ISS-nnn (highest number cited anywhere, plus one)
  e               next free errata number E<n> (defined as `**E<n>.` in docs 11 and 16)
  --where         also list every ref/worktree that holds the highest id
  --suffix-of ID  print the first free lettered suffix of ID instead (ISS-088 -> ISS-088b)
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ISS_PATHS = ("docs/vss-integration", "docs/plans", "docs/superpowers")
ERRATA_PATHS = (
    "docs/vss-integration/11-errata-2026-09-23.md",
    "docs/vss-integration/16-errata-2026-10-03.md",
)
ISS_RE = re.compile(r"\bISS-(\d+)([a-z]?)\b")
E_DEF_RE = re.compile(r"(?m)^\*\*E(\d+)\.")


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )
    return done.stdout if done.returncode in (0, 1) else ""


def refs(repo: Path) -> list[str]:
    out = git(repo, "for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes")
    return [r for r in out.split() if not r.endswith("/HEAD")]


def worktrees(repo: Path) -> list[Path]:
    paths = [
        Path(line.split(" ", 1)[1])
        for line in git(repo, "worktree", "list", "--porcelain").splitlines()
        if line.startswith("worktree ")
    ]
    return paths or [repo]


def sources(repo: Path, paths: tuple[str, ...], pattern: re.Pattern[str]) -> dict[str, str]:
    """Map source label -> concatenated text of the watched paths, for each ref and worktree."""
    found: dict[str, str] = {}
    for ref in refs(repo):
        text = git(repo, "grep", "-h", "-I", "-e", ".", ref, "--", *paths)
        if not text:
            continue
        # `git grep ... REF` prefixes nothing under -h; keep only lines that can matter
        found[ref] = "\n".join(line for line in text.splitlines() if pattern.search(line))
    for wt in worktrees(repo):
        chunks = []
        for rel in paths:
            base = wt / rel
            files = (
                [base] if base.is_file() else sorted(base.rglob("*.md")) if base.is_dir() else []
            )
            chunks.extend(f.read_text(encoding="utf-8", errors="replace") for f in files)
        found[f"worktree:{wt}"] = "\n".join(chunks)
    return found


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("kind", choices=("iss", "e"))
    ap.add_argument("--repo", default=".")
    ap.add_argument("--where", action="store_true")
    ap.add_argument("--suffix-of")
    args = ap.parse_args(argv[1:])
    repo = Path(args.repo).resolve()

    if args.kind == "e":
        by_source = sources(repo, ERRATA_PATHS, E_DEF_RE)
        numbers = {src: {int(n) for n in E_DEF_RE.findall(text)} for src, text in by_source.items()}
        top = max((n for ns in numbers.values() for n in ns), default=0)
        print(f"E{top + 1}")
        if args.where:
            for src, ns in numbers.items():
                if top in ns:
                    print(f"E{top} is held by {src}")
        return 0

    by_source = sources(repo, ISS_PATHS, ISS_RE)
    held: dict[str, set[tuple[int, str]]] = {
        src: {(int(n), s) for n, s in ISS_RE.findall(text)} for src, text in by_source.items()
    }
    if args.suffix_of:
        m = re.fullmatch(r"ISS-(\d+)", args.suffix_of)
        if not m:
            print("--suffix-of takes a bare id such as ISS-088", file=sys.stderr)
            return 2
        base = int(m.group(1))
        used = {s for ids in held.values() for n, s in ids if n == base and s}
        letter = next(c for c in "bcdefghijklmnopqrstuvwxyz" if c not in used)
        print(f"ISS-{base:03d}{letter}")
        return 0
    top = max((n for ids in held.values() for n, _ in ids), default=0)
    print(f"ISS-{top + 1:03d}")
    if args.where:
        for src, ids in held.items():
            if any(n == top for n, _ in ids):
                print(f"ISS-{top:03d} is held by {src}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
