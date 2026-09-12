#!/usr/bin/env python3
"""Collection-sanity gate (fast-confidence-loop spec §5.3).

Fails when any TRACKED test file is zero bytes, or collects zero tests.
Three zero-byte test files sat undetected on main during M1 because the
frontend CI job exit-0s on its first summary line; this script makes that
state red within one push, independently of any job-level hack.

Usage: check-test-collection.py PATH [PATH ...] [--allow ID[,ID...]] [--allowlist FILE]
Exit: 0 clean, 1 findings, 2 operational error (git missing, collection crash).

Persistent exemptions live in scripts/collection-sanity-allowlist.txt beside
this script: one id per line, `#` starts the tracking-ref comment (ruling
R-FCL-T1-ALLOWLIST). A missing file is an empty allowlist; --allowlist FILE
points somewhere else (tests use that to stay off the repo's file); --allow
entries add on top and stay emergency-only — each allowed id must also appear
in .github/workflows/flake-allowlist.yml with a tracking ref (enforced in Task 2).
"""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from pathlib import Path

PY_SUFFIXES = (".py",)
JS_SUFFIXES = (".ts", ".tsx", ".js", ".jsx")

ALLOWLIST_FILENAME = "collection-sanity-allowlist.txt"


def tracked_files(roots: list[str]) -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z", *roots], capture_output=True, text=True, check=True
    )
    return [Path(p) for p in out.stdout.split("\0") if p]


def is_test_file(p: Path) -> bool:
    name = p.name
    if p.suffix in PY_SUFFIXES:
        return name.startswith("test_")
    if p.suffix in JS_SUFFIXES:
        return ".test." in name or ".spec." in name
    return False


def module_path_is_test(dotted: str) -> bool:
    """True when a dotted module path's last component names a test_* module.

    backend.tests.integration.test_system_api -> test_system_api (test module).
    backend.services.system -> system (not). Relative sources (`from .x import *`)
    carry the same last component, so the same test applies to them.
    """
    return dotted.rpartition(".")[2].startswith("test_")


def imports_test_symbols(node: ast.ImportFrom | ast.Import) -> bool:
    """Does this import statement bring in test symbols from a test_* module?

    Pytest collects tests re-exported from other test modules: a test_*.py that
    does `from backend.tests.integration.test_system_api import *` or imports a
    named Test* class from a sibling test module collects whatever arrives.
    Subtracting those import sources from the "defines no test symbols" verdict
    keeps re-export shims (and their 74-test real collections) out of the
    findings. Only imports FROM a test_* module count — importing pytest or a
    service module named like a test target does not.

    Blind spot (heuristic, accepted): whether the imported names are actually
    tests (Test* class / test_* function) is not resolved — a test_* module
    importing a *helper* from another test_* module would count as "collects".
    The flag is a heuristic preflight, not real collection; the pytest jobs own
    the truly-empty class. Resolution via import execution is deliberately out
    of scope (docstring above).
    """
    if isinstance(node, ast.ImportFrom):
        # `from x import *` / `from .x import *` / `from x import TestA, test_b`,
        # and `from . import test_helpers` (relative with module=None)
        return (node.module is not None and module_path_is_test(node.module)) or any(
            module_path_is_test(alias.name) for alias in node.names
        )
    return any(module_path_is_test(alias.name) for alias in node.names)


def py_collects_tests(p: Path) -> tuple[bool, str | None]:
    """(ok, reason). AST heuristic: file must define a Test* class or test_* function,
    or pull them in transitively from another test_* module.

    Deliberately syntactic: import-time side effects (env probes, container
    boots) make real collection too slow/expensive for a preflight. A file
    that defines tests but errors on import stays this gate's blind spot by
    design; the pytest jobs catch that class.
    """
    try:
        tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError as exc:
        return True, f"SyntaxError: {exc}"
    imports_test_names = False
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            return True, None
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
            "test"
        ):
            return True, None
        if isinstance(node, ast.ImportFrom | ast.Import) and imports_test_symbols(node):
            imports_test_names = True
    if imports_test_names:
        return True, None
    return True, "no test_* function or Test* class defined"


def load_allowlist(path: Path) -> set[str]:
    """Read one id per line; '#' starts the tracking-ref comment (R-FCL-T1-ALLOWLIST).

    Malformed-entry tolerance: blank/comment-only lines are skipped; anything
    else is kept as an id verbatim, so a typo'd id simply fails to match and
    the finding surfaces — never silently swallowed.
    """
    out: set[str] = set()
    if not path.exists():
        return out  # missing file = empty allowlist (tmp-tree tests unaffected)
    for line in path.read_text(encoding="utf-8").splitlines():
        ident = line.split("#", 1)[0].strip()
        if ident:
            out.add(ident)
    return out


def findings_for(paths: list[Path]) -> list[str]:
    out = []
    for p in paths:
        if not is_test_file(p):
            continue
        try:
            size = p.stat().st_size
        except FileNotFoundError:
            continue  # tracked-but-deleted in this worktree: not this gate's problem
        if size == 0:
            out.append(f"{p}: zero bytes")
        elif p.suffix in PY_SUFFIXES:
            ok, reason = py_collects_tests(p)
            if reason:
                out.append(f"{p}: {reason}")
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+")
    ap.add_argument("--allow", default="", help="comma-separated emergency opt-outs")
    ap.add_argument(
        "--allowlist",
        type=Path,
        default=Path(__file__).resolve().parent / ALLOWLIST_FILENAME,
        help="allowlist file (default: collection-sanity-allowlist.txt beside this script)",
    )
    args = ap.parse_args(argv[1:])
    allowed = load_allowlist(args.allowlist) | {
        a.strip() for a in args.allow.split(",") if a.strip()
    }
    files = tracked_files(args.roots)
    findings = [f for f in findings_for(files) if f.split(":", 1)[0] not in allowed]
    for f in findings:
        print(f"COLLECTION-SANITY: {f}", file=sys.stderr)
    if findings:
        print(
            f"COLLECTION-SANITY: {len(findings)} file(s) would collect zero tests. "
            "Write tests, delete the file, or add an allowlist entry with a tracking ref.",
            file=sys.stderr,
        )
        return 1
    print(f"collection-sanity: {len(files)} tracked files scanned, all collect >= 1 test")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
