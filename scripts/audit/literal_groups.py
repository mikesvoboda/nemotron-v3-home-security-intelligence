#!/usr/bin/env python3
"""Literal-duplicate group census (O1.7): committed scanner for the 00-audit §6 figure.

The audit's §6 "Parametrize candidates. 488 groups of 3+ tests differing only
in literals: 2,010 functions in 247 files" was an uncommitted scan; BB.1
consolidates against it. The package says reuse scripts/parametrize-guard.py
where it fits — and it fits the HARD part: the masked-AST body identity
(literals → sentinel, method name canonicalized, call graph and def/async-def
shape preserved) and the pytest.raises(match=) bucket guard that keeps the
"41 false-identical" lesson from folding distinct assertions into one list.
This script imports those two functions rather than re-deriving them.

Where it differs from the guard, deliberately: the guard is a per-class
merge-safety REPORT for a consolidation ledger, defaulting to classes of >= 8
methods. The audit figure counts GROUPS OF >= 3 BODY-IDENTICAL methods
across the whole tree, whether or not their class is large — so the cluster
size floor here is 3 (configurable) and class size is irrelevant. "Group" is
(file, class, masked-body, raises-bucket), exactly the guard's bucket key;
module-level test functions bucket under class "".

Output: JSON on stdout (groups, functions, files + per-group rows), summary
line on stderr. Exit 0; parse failure loud (exit 1) — same hard rule as the
guard.

Run:    uv run python scripts/audit/literal_groups.py [--root REPO] [--min 3]
Test:   uv run python -m pytest scripts/audit/test_literal_groups.py -q
"""

from __future__ import annotations

import argparse
import ast
import collections
import importlib.util
import json
import sys
from pathlib import Path

AUDIT_DIR = Path(__file__).resolve().parent
REPO_ROOT = AUDIT_DIR.parents[1]
GUARD_PATH = REPO_ROOT / "scripts" / "parametrize-guard.py"

# Same set as the sibling censuses (battery_census/settings_orphans/retired_names).
# Measured the first run WITHOUT the .venv entry: 103 of 605 groups lived in
# installed packages' own test files (1,831 test_*.py under .venv here) — a
# census that counts whatever pip resolved is not reproducible across machines
# or CI runs, and one vendor file using newer syntax would trip the loud
# SyntaxError exit below on every run. The audit's 488 was a repo-tree figure;
# the venv inflation accounted for most of the gap.
SKIP_DIRNAMES = {".git", "__pycache__", "node_modules", ".venv", ".pytest_cache", ".mypy_cache"}


def _load_guard():
    spec = importlib.util.spec_from_file_location("parametrize_guard", GUARD_PATH)
    assert spec and spec.loader, f"cannot load {GUARD_PATH}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def groups_in_file(path: Path, guard, min_size: int) -> list[dict]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    buckets: dict[tuple[str, str, tuple[str, ...]], list] = collections.defaultdict(list)

    def add(fn, cls_name):
        if not fn.name.startswith("test_"):
            return
        buckets[(cls_name, guard._masked(fn), guard.raises_matches(fn))].append(fn)

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for m in node.body:
                if isinstance(m, ast.FunctionDef | ast.AsyncFunctionDef):
                    add(m, node.name)
    # module-level tests bucket under class "". tree.body is top-level
    # statements only — class methods never appear directly in it — so no
    # de-duplication against the class pass above is needed.
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            add(node, "")
    out = []
    for (cls, _body, matches), members in buckets.items():
        if len(members) >= min_size:
            out.append(
                {
                    "file": path.relative_to(REPO_ROOT).as_posix() if path.is_relative_to(REPO_ROOT) else str(path),
                    "class": cls,
                    "size": len(members),
                    "members": sorted(m.name for m in members),
                    "raises_match": list(matches),
                }
            )
    return out


def census(root: Path, min_size: int) -> dict:
    guard = _load_guard()
    rows = []
    try:
        for path in sorted(root.rglob("test_*.py")):
            if any(part in SKIP_DIRNAMES for part in path.relative_to(root).parts[:-1]):
                continue
            rows.extend(groups_in_file(path, guard, min_size))
    except SyntaxError as e:  # loud per the guard's own hard rule
        print(f"[ERROR] parse failure: {e}", file=sys.stderr)
        raise SystemExit(1) from None
    rows.sort(key=lambda r: -r["size"])
    return {
        "min_group_size": min_size,
        "groups": len(rows),
        "functions": sum(r["size"] for r in rows),
        "files": len({r["file"] for r in rows}),
        "groups_detail": rows,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=REPO_ROOT)
    ap.add_argument("--min", type=int, default=3, help="minimum group size (audit figure used 3)")
    args = ap.parse_args(argv)
    if not args.root.is_dir():
        print(f"[ERROR] --root {args.root} is not a directory", file=sys.stderr)
        return 1
    result = census(args.root, args.min)
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    print(file=sys.stdout)
    print(
        f"O1.7 literal-groups: {result['groups']} groups of >={args.min} tests differing "
        f"only in literals — {result['functions']} functions in {result['files']} files",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
