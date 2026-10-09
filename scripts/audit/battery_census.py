#!/usr/bin/env python3
"""Mutation-battery census (O1.7): committed scanner for the 00-audit §6 battery figures.

The audit's §6 headline — "130 files named test_<module>_batchNN[_x].py
(120,913 lines, 3,240 tests)" — is the number Phase 4 consolidation is planned
around, and it was never committed. This script enumerates the battery and
per-file: lines, collected test count, and the target module the battery is
named after.

Battery detection: file basename matches test_<module>_batch<NN>[suffix]*.py
(the audit's own pattern; `_batch28_22.py` style sequence suffixes AND the
bare letter suffixes — `test_logs_batch13b.py` — included; the contract's
glob is `test_*_batchNN*.py` and a first version of this regex required a
separator before the suffix, silently dropping the 8 letter-suffixed
batteries, 1,758 lines, which is exactly the silent skip AGENTS.md forbids).
The target module is the <module> segment — the module whose mutants the
battery was written to kill (documented convention: the batteries cite
mutmut run ids naming that module).

Test count: AST-collected — top-level and Test*-class functions starting with
test_, plus one per parametrize-set member multiplied through stacked
parametrize decorators (decorator lists are rare here; a parametrize whose
argument is not a literal list is counted as 1 and flagged). This is a
collection-free count on purpose: it runs without importing backend.

Output: JSON on stdout (file_count, total_lines, total_tests, per-file rows),
summary line on stderr. Exit 0; parse failure is loud (exit 1).

Run:    uv run python scripts/audit/battery_census.py [--root REPO]
Test:   uv run python -m pytest scripts/audit/test_battery_census.py -q
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

BATTERY_RE = re.compile(r"^test_(?P<module>.+?)_batch\d+[a-z]*(?:[_+.]\w+)*\.py$")
SKIP_DIRNAMES = {".git", "__pycache__", "node_modules", ".venv", ".pytest_cache", ".mypy_cache"}


def _parametrize_multiplier(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[int, bool]:
    """Product of literal parametrize arg lengths; (1, False) when none.

    The flag marks a non-literal arg counted as 1 (a bare `range()` or name is
    not expanded without evaluation — flagged, never silently guessed).
    """
    mult, flagged = 1, False
    for dec in fn.decorator_list:
        if not (isinstance(dec, ast.Call) and ast.unparse(dec.func).endswith("parametrize")):
            continue
        for arg in dec.args[1:]:
            if isinstance(arg, (ast.List, ast.Tuple, ast.Set)):
                mult *= max(len(arg.elts), 1)
            else:
                flagged = True
                mult *= 1
    return mult, flagged


def count_tests(path: Path) -> tuple[int, int]:
    """(test_functions, flagged_parametrizes) for one file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    count, flagged = 0, 0
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith("test_"):
            mult, was_flagged = _parametrize_multiplier(node)
            count += mult
            flagged += 1 if was_flagged else 0
    return count, flagged


def census(root: Path) -> dict:
    rows = []
    for path in sorted(root.rglob("test_*.py")):
        rel = path.relative_to(root).as_posix()
        if any(part in SKIP_DIRNAMES for part in path.relative_to(root).parts[:-1]):
            continue
        m = BATTERY_RE.match(path.name)
        if not m:
            continue
        n_tests, flagged = count_tests(path)
        rows.append(
            {
                "path": rel,
                "module": m.group("module"),
                "lines": len(path.read_text(encoding="utf-8").splitlines()),
                "tests": n_tests,
                "flagged_parametrize": flagged,
            }
        )
    return {
        "file_count": len(rows),
        "total_lines": sum(r["lines"] for r in rows),
        "total_tests": sum(r["tests"] for r in rows),
        "flagged_files": sum(1 for r in rows if r["flagged_parametrize"]),
        "files": rows,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = ap.parse_args(argv)
    if not args.root.is_dir():
        print(f"[ERROR] --root {args.root} is not a directory", file=sys.stderr)
        return 1
    try:
        result = census(args.root)
    except SyntaxError as e:
        print(f"[ERROR] parse failure: {e}", file=sys.stderr)
        return 1
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    print(file=sys.stdout)
    print(
        f"O1.7 battery-census: {result['file_count']} battery files, "
        f"{result['total_lines']} lines, {result['total_tests']} tests"
        + (f", {result['flagged_files']} with non-literal parametrize args" if result["flagged_files"] else ""),
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
