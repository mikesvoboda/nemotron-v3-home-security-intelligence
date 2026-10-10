#!/usr/bin/env python3
"""Retired-name hit census (O1.7): committed scanner for the 00-audit retired-name counts.

The audit's retired-name figures (§2 "29 still describe Florence", §8 "retired
components appear in 70 non-archive docs and 29 AGENTS.md files") came from
scans nobody committed — the exact gap contract rule 3 names, because B3.3,
W1.1 and W3.3 compare before/after counts against them. This script is the
scan view those numbers must be re-measured under.

Retired names — the five §O1.7 names, pinned against the plan text by a test:
florence, nemotron, enrichment, pose, demographic. NOT the validator's
retired_name_baseline, which is a different five (it gates AGENTS.md ceilings:
xclip and plural demographics instead of pose and demographic — measured
while writing this census).

Matching is the validator's own rule, copied from count_retired_names:
whole-word, case-insensitive (``\\b{name}\\b`` over the lowered text). The
validator's doctrine comment is load-bearing and was adopted verbatim in
spirit: "a substring implementation measures a different quantity than the
plan named" — measured here on the first run, a substring rule matched
``compose`` for ``pose`` (every docker-compose*.yml, every prose "compose")
and ``GPU_FLORENCE``-style identifiers for ``florence``: 2,350 files, inflated
past belief. Whole-word consequence pinned by test: identifiers like
``florence_url`` and ``florence2`` are NOT hits (``_`` and digits are \\w) —
this census counts text that *names* the retired system, matching the gate
that already polices the same residue.

Buckets (exactly one per file, precedence first match):
  agents    — basename is AGENTS.md anywhere in the tree.
  docs      — a LIVING doc: under ``docs/``, markdown (.md), outside the dated
              record trees the retired-paths gate exempts (docs/plans/,
              docs/superpowers/, docs/vss-integration/, docs/uplevel/) plus
              the dated goal prompts (docs/goal-prompt-*.txt). Records are
              history and B3.3/W1.1/W3.3 do not edit them; counting them
              would measure the wrong corpus.
  code      — anything else that is text: sources, tests, workflows, configs,
              scripts. (Tests count as code: deleting a retired name from a
              test is part of W1.1's before/after.)
Binary-ish extensions (images, lockfiles excluded by extension list below)
are skipped, never grepped blind.

Output: JSON on stdout (per-bucket file counts + per-name totals + the file
list), one summary line on stderr. Exit 0; a read failure is loud (exit 1),
never a silent skip.

Run:    uv run python scripts/audit/retired_names.py [--root REPO]
Test:   uv run python -m pytest scripts/audit/test_retired_names.py -q
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

NAMES = ["florence", "nemotron", "enrichment", "pose", "demographic"]
# Whole-word, over the lowered text — the validator's rule verbatim in shape.
NAME_PATTERNS = {name: re.compile(rf"\b{re.escape(name)}\b") for name in NAMES}

RECORD_DOC_PREFIXES = (
    "docs/plans/",
    "docs/superpowers/",
    "docs/vss-integration/",
    "docs/uplevel/",
)
DOC_SUFFIXES = {".md"}
# Extensionless files (Makefile, Dockerfile…) and ordinary text are scanned;
# these extensions are machine artifacts or archives — skipped loudly by name.
SKIP_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".gz",
    ".tgz",
    ".bz2",
    ".xz",
    ".pyc",
    ".woff",
    ".woff2",
    ".ttf",
    ".so",
    ".dylib",
    ".bin",
    ".mp4",
    ".mov",
}
SKIP_DIRNAMES = {".git", "__pycache__", "node_modules", ".venv", ".pytest_cache", ".mypy_cache"}


def classify(rel: str) -> str | None:
    """One bucket per file, or None when the file is out of scope."""
    name = rel.rsplit("/", 1)[-1]
    if name == "AGENTS.md":
        return "agents"
    suffix = Path(rel).suffix.lower()
    if suffix in SKIP_SUFFIXES:
        return None
    if rel.startswith("docs/"):
        if suffix not in DOC_SUFFIXES:
            return None
        if rel.startswith(RECORD_DOC_PREFIXES) or name.startswith("goal-prompt-"):
            return None
        return "docs"
    return "code"


def scan(root: Path) -> dict:
    per_name: dict[str, int] = {n: 0 for n in NAMES}
    buckets: dict[str, int] = {"agents": 0, "docs": 0, "code": 0}
    # bucket x name cross-tab: the audit's own figures are per-name-within-
    # per-bucket ("29 still describe Florence" = florence in AGENTS.md), and
    # every [C] value 00-audit.md carries must be regenerable from this
    # script's JSON alone — a committed number the committed script cannot
    # print is the rule-3 gap this package exists to close.
    buckets_per_name: dict[str, dict[str, int]] = {
        b: {n: 0 for n in NAMES} for b in buckets
    }
    files: list[dict] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if any(part in SKIP_DIRNAMES for part in path.relative_to(root).parts[:-1]):
            continue
        bucket = classify(rel)
        if bucket is None:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace").lower()
        except OSError as e:  # loud per hard rule
            print(f"[ERROR] unreadable {rel}: {e}", file=sys.stderr)
            raise SystemExit(1) from None
        hits = [n for n in NAMES if NAME_PATTERNS[n].search(text)]
        if not hits:
            continue
        buckets[bucket] += 1
        for n in hits:
            per_name[n] += 1
            buckets_per_name[bucket][n] += 1
        files.append({"path": rel, "bucket": bucket, "names": hits})
    return {
        "names": NAMES,
        "files_with_hits": len(files),
        "buckets": buckets,
        "hits_per_name": per_name,
        "buckets_per_name": buckets_per_name,
        "files": files,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = ap.parse_args(argv)
    if not args.root.is_dir():
        print(f"[ERROR] --root {args.root} is not a directory", file=sys.stderr)
        return 1
    result = scan(args.root)
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    print(file=sys.stdout)
    b = result["buckets"]
    print(
        f"O1.7 retired-names: {result['files_with_hits']} files with hits "
        f"(agents {b['agents']}, living docs {b['docs']}, code {b['code']})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
