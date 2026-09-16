#!/usr/bin/env python3
"""Census every test-suppression escape hatch in the tree (WP1.1).

SPEC (docs/superpowers/specs/2026-09-15-test-platform-improvement-design.md
§escape hatches) baselines the categories at: 6 / 0 / 16 / 32 / 63 / 4 / 94 /
54 / 4 trees / 5 modules. This script re-derives each number mechanically so
Phase 1's ratchet (WP1.3) has one machine-readable source of truth: counts may
only FALL, and every surviving suppression must carry owner+expiry in the
registry (WP1.2).

Count definitions (fixtures in scripts/test_suppression_census.py pin each):

  collection_allowlist   non-comment, non-blank lines of
                         scripts/collection-sanity-allowlist.txt
  flake_allowlist        entries under `flakes:` in .github/flake-allowlist.yml
  frontend_quarantine    concrete-file entries in vite.config.ts's `exclude:`
                         list — glob-tree entries (tests/e2e/**,
                         tests/contract/**) are structural, not quarantines
  pytest_skip / pytest_skipif / pytest_xfail
                         AST decorator calls (pytest.mark.skip[if|xfail]),
                         any form (bare or with arguments)
  pytest_skip_imperative AST Call nodes to pytest.skip(...)
  frontend_skip / frontend_only / frontend_todo
                         `.skip`/`.only`/`.todo` call/member sites in
                         frontend test files (vitest/jest idiom)
  excluded_test_trees    pytest test trees excluded from the default runs by
                         validate.sh's --ignore flags (deduped basenames:
                         load, benchmarks, e2e, chaos)
  coverage_omit          concrete production modules in pyproject's
                         [tool.coverage.run] omit (wildcard patterns are
                         plumbing; backend/main.py is app wiring, not an
                         untested module — the spec's 5 counts the modules
                         listed under the "need tests"/"requires testing"
                         comments)

Usage:
    ./scripts/suppression-census.py            # JSON to stdout
    ./scripts/suppression-census.py --expect JSON  # exit 1 on any category mismatch (CI)
    ./scripts/suppression-census.py --root DIR # census another tree (fixtures)
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

REPO_ROOT_DEFAULT = Path(__file__).resolve().parent.parent

CATEGORIES = [
    "collection_allowlist",
    "flake_allowlist",
    "frontend_quarantine",
    "pytest_skip",
    "pytest_skipif",
    "pytest_xfail",
    "pytest_skip_imperative",
    "frontend_skip",
    "frontend_only",
    "frontend_todo",
    "excluded_test_trees",
    "coverage_omit",
]


def count_collection_allowlist(root: Path) -> int:
    path = root / "scripts/collection-sanity-allowlist.txt"
    return sum(
        1
        for line in path.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def count_flake_allowlist(root: Path) -> int:
    import yaml  # repo dev dep; census is a dev tool, import-in-function keeps it optional

    data = yaml.safe_load((root / ".github/flake-allowlist.yml").read_text())
    return len((data or {}).get("flakes") or [])


_VITE_EXCLUDE_RE = re.compile(r"exclude:\s*\[(.*?)\]", re.DOTALL)


def count_frontend_quarantine(root: Path) -> int:
    text = (root / "frontend/vite.config.ts").read_text()
    # The quarantine is the exclude list that SPREADS configDefaults.exclude
    # (vitest's test-exclude). vite.config.ts carries three exclude arrays
    # (optimizeDeps, test, coverage) — anchoring on the spread is the stable
    # identity, not line numbers.
    for m in _VITE_EXCLUDE_RE.finditer(text):
        body = m.group(1)
        if "configDefaults.exclude" not in body:
            continue
        entries = re.findall(r"'([^']+)'", body)
        # Glob-tree entries (tests/e2e/**, tests/contract/**) are structural
        # directory exclusions, not per-file quarantines.
        return sum(1 for e in entries if "**" not in e)
    return 0


def _decorator_name(node: ast.expr) -> str | None:
    """Dotted name of a decorator, unwrapping a call (pytest.mark.xfail(...) -> pytest.mark.xfail)."""
    target = node.func if isinstance(node, ast.Call) else node
    parts: list[str] = []
    while isinstance(target, ast.Attribute):
        parts.append(target.attr)
        target = target.value
    if isinstance(target, ast.Name):
        parts.append(target.id)
        return ".".join(reversed(parts))
    return None


def _count_decorators(tree_files: list[Path], marker: str) -> int:
    """Count `@pytest.mark.<marker>` decorators in any form (bare, (), with kwargs).

    Also counts the bare `@mark.<marker>` idiom (`from pytest import mark`) —
    census must not undercount an equivalent spelling.
    """
    n = 0
    for path in tree_files:
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError, OSError:
            continue
        for node in ast.walk(tree):
            decorators = getattr(node, "decorator_list", [])
            for dec in decorators:
                name = _decorator_name(dec)
                if name in {f"pytest.mark.{marker}", f"mark.{marker}"}:
                    n += 1
    return n


def _call_name(node: ast.expr) -> str | None:
    return _decorator_name(node)


def count_pytest_skip_imperative(tree_files: list[Path]) -> int:
    n = 0
    for path in tree_files:
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError, OSError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = _call_name(node.func)
                if name in ("pytest.skip", "_pytest.skipping.skip"):
                    n += 1
    return n


_FRONTEND_SUPPRESSION_RE = re.compile(r"\.(skip|only|todo)\b")


def _frontend_test_files(root: Path) -> list[Path]:
    """Vitest suite only (frontend/src). frontend/tests/e2e is the Playwright
    runner — a different suppressible tree, and the spec's baseline (54, with
    .only 0 / .todo 0) is the vitest count; e2e suppression is governed by
    the excluded-trees category instead."""
    files: list[Path] = []
    base = root / "frontend/src"
    if base.exists():
        files += [p for p in base.rglob("*.ts*") if re.search(r"\.(test|spec)\.tsx?$", p.name)]
    return files


def count_frontend_modifiers(root: Path) -> tuple[int, int, int]:
    skip = only = todo = 0
    for path in _frontend_test_files(root):
        text = path.read_text()
        for m in _FRONTEND_SUPPRESSION_RE.finditer(text):
            kind = m.group(1)
            if kind == "skip":
                skip += 1
            elif kind == "only":
                only += 1
            else:
                todo += 1
    return skip, only, todo


def count_excluded_test_trees(root: Path) -> int:
    """Deduped basenames of test trees excluded by validate.sh --ignore flags."""
    text = (root / "scripts/validate.sh").read_text()
    names = set()
    for m in re.finditer(r"--ignore=(\S+)", text):
        tail = m.group(1).rstrip("\\").strip("'\"")
        # backend/tests/load/ or backend/tests/load/\` -> load
        parts = [p for p in tail.split("/") if p]
        if parts:
            names.add(parts[-1].rstrip("\\"))
    return len(names)


def count_coverage_omit(root: Path) -> int:
    """Concrete production modules in [tool.coverage.run] omit.

    Plumbing exclusions (wildcards) and the app entry point (backend/main.py,
    wiring + lifespan, exercised as the ASGI app in integration) are not
    "production modules without tests" — the spec's count of 5 is the explicit
    module files under the suppression comments.
    """
    text = (root / "pyproject.toml").read_text()
    m = re.search(r"\[tool\.coverage\.run\].*?omit\s*=\s*\[(.*?)\]", text, re.DOTALL)
    if not m:
        return 0
    entries = re.findall(r'"([^"]+)"', m.group(1))
    return sum(
        1
        for e in entries
        if "*" not in e
        and e != "backend/main.py"
        and e.startswith("backend/")
        and not e.startswith("backend/tests")
    )


def census(root: Path) -> dict[str, int]:
    backend_tests = sorted((root / "backend/tests").rglob("*.py"))
    skip, only, todo = count_frontend_modifiers(root)
    return {
        "collection_allowlist": count_collection_allowlist(root),
        "flake_allowlist": count_flake_allowlist(root),
        "frontend_quarantine": count_frontend_quarantine(root),
        "pytest_skip": _count_decorators(backend_tests, "skip"),
        "pytest_skipif": _count_decorators(backend_tests, "skipif"),
        "pytest_xfail": _count_decorators(backend_tests, "xfail"),
        "pytest_skip_imperative": count_pytest_skip_imperative(backend_tests),
        "frontend_skip": skip,
        "frontend_only": only,
        "frontend_todo": todo,
        "excluded_test_trees": count_excluded_test_trees(root),
        "coverage_omit": count_coverage_omit(root),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Count every test-suppression escape hatch")
    parser.add_argument(
        "--root", default=str(REPO_ROOT_DEFAULT), help="Tree to census (default: repo root)"
    )
    parser.add_argument(
        "--expect",
        help="JSON object of category->count; exit 1 on any mismatch (CI stability/staleness check)",
    )
    args = parser.parse_args()

    result = census(Path(args.root))
    print(json.dumps(result, indent=2, sort_keys=True))

    if args.expect:
        expected = json.loads(args.expect)
        mismatches = {k: (result.get(k), v) for k, v in expected.items() if result.get(k) != v}
        if mismatches:
            for cat, (got, want) in sorted(mismatches.items()):
                print(f"MISMATCH {cat}: census={got} expected={want}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
