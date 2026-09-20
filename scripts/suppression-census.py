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
  unspecced_patch        convertible-but-unspecced mock.patch sites under
                         backend/tests (WP4.2). Measured by
                         scripts/check-mock-spec.py, which reuses autospec-
                         sweep's classifier — one definition of "convertible"
                         for sweep, gate, census, and ratchet.
  tpa_slow_list          exemption patterns in scripts/audit-test-durations.py's
                         SLOW_TEST_PATTERNS — the Test Performance Audit's
                         tracked-slow list, a 60s cap instead of the category
                         threshold (WP1.3: was 150 uncounted patterns, ~80%
                         not slow, pruning to the 7 measured breaches; every
                         future entrant is now a registry entry with a
                         measured-corpus reason and an expiry).

Usage:
    ./scripts/suppression-census.py            # JSON to stdout
    ./scripts/suppression-census.py --expect JSON  # exit 1 on any category mismatch (CI)
    ./scripts/suppression-census.py --locations    # full inventory, WP1.2's key
    ./scripts/suppression-census.py --root DIR     # census another tree (fixtures)
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
    "unspecced_patch",
    "tpa_slow_list",
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


def _tpa_slow_list_locations(root: Path) -> list[dict]:
    """Patterns in audit-test-durations.py's SLOW_TEST_PATTERNS (WP1.3).

    Root-relative on purpose: unlike the other importlib-reuse channels this
    one walks the tree's OWN copy of the script, because the patterns ARE the
    suppression — a fixture tree that injects a 2-pattern audit script gets a
    2-pattern count. The reason text is the trailing `# ...` comment on each
    pattern line (the measured-brief the entry earned its slot with), which
    registry-gen's kind-rules classify.
    """
    script = root / "scripts" / "audit-test-durations.py"
    if not script.exists():
        return []
    src = script.read_text()
    tree = ast.parse(src)
    src_lines = src.splitlines()
    out = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "SLOW_TEST_PATTERNS" for t in node.targets)
            and isinstance(node.value, ast.List)
        ):
            for elt in node.value.elts:
                if not (isinstance(elt, ast.Constant) and isinstance(elt.value, str)):
                    continue
                reason = ""
                last = src_lines[elt.end_lineno - 1]
                m = re.search(r"['\"],?\s*#\s*(.+?)\s*$", last)
                if m:
                    reason = m.group(1)
                # id-keyed like every other channel — no line numbers, they drift
                out.append({"id": elt.value, "reason": reason or "no reason comment"})
    return out


def _rel(root: Path, p: Path) -> str:
    return p.relative_to(root).as_posix()


def _collection_allowlist_locations(root: Path) -> list[dict]:
    path = root / "scripts/collection-sanity-allowlist.txt"
    out = []
    for line in path.read_text().splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        # Format: <path>  # <tracking-ref> — the comment is the reason field.
        file_part, _, ref = s.partition("#")
        out.append({"id": file_part.strip(), "reason": ref.strip()})
    return out


def _flake_allowlist_locations(root: Path) -> list[dict]:
    import yaml

    data = yaml.safe_load((root / ".github/flake-allowlist.yml").read_text())
    return [
        {"id": str(e.get("id", "")), "reason": str(e.get("note", "") or "")}
        for e in ((data or {}).get("flakes") or [])
    ]


def _frontend_quarantine_locations(root: Path) -> list[dict]:
    text = (root / "frontend/vite.config.ts").read_text()
    for m in _VITE_EXCLUDE_RE.finditer(text):
        body = m.group(1)
        if "configDefaults.exclude" not in body:
            continue
        entries = re.findall(r"'([^']+)'", body)
        return [{"id": e, "reason": ""} for e in entries if "**" not in e]
    return []


def _module_str_constants(tree: ast.Module) -> dict[str, str]:
    """{name: value} for top-level NAME = <string constant> assignments.

    Reason texts are commonly factored into a module constant when several
    decorators share one — the real MQTT_PUMP_REASON / EXPORTDEFER_REASON
    shape. A locations pass that only reads ast.Constant loses those
    reasons, and WP1.2's registry cannot classify what it cannot read.
    """
    consts: dict[str, str] = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            try:
                value = ast.literal_eval(node.value)
            except ValueError, SyntaxError:
                continue
            if isinstance(value, str):
                consts[node.targets[0].id] = value
    return consts


def _decorator_reason(dec: ast.expr, consts: dict[str, str] | None = None) -> str:
    """The reason= kwarg of a decorator call, '' for bare or reason-less forms.

    A Name value resolves through the module's string constants (same-file
    indirection only — imports are out of scope for a census).
    """
    if isinstance(dec, ast.Call):
        for kw in dec.keywords:
            if kw.arg == "reason":
                if isinstance(kw.value, ast.Constant):
                    return str(kw.value.value)
                if isinstance(kw.value, ast.Name) and consts:
                    return consts.get(kw.value.id, "")
    return ""


def _qualified_names(tree: ast.Module) -> dict[int, str]:
    """id(node) -> qualified dotted name for every decorator-bearing node.

    Registry ids key on file::<qualname>, NOT the bare method name: two
    classes can each define a method of the same name (test_system_models.py
    ships 7 such pairs) and bare-name ids COLLIDE — registry entries overwrite
    each other and the ratchet can't license sites individually. pytest's own
    node ids qualify with the class, so the census does too.
    """
    names: dict[int, str] = {}

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
                name = prefix + child.name
                names[id(child)] = name
                visit(child, name + "::")
            else:
                visit(child, prefix)

    visit(tree, "")
    return names


def _decorator_locations(tree_files: list[Path], root: Path, marker: str) -> list[dict]:
    """file::[Class::]test_name ids — line-number-drift-proof, collision-proof."""
    out = []
    for path in tree_files:
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError, OSError:
            continue
        consts = _module_str_constants(tree)
        names = _qualified_names(tree)
        for node in ast.walk(tree):
            seen_on_node = 0
            for dec in getattr(node, "decorator_list", []):
                name = _decorator_name(dec)
                if name in {f"pytest.mark.{marker}", f"mark.{marker}"}:
                    seen_on_node += 1
                    suffix = "" if seen_on_node == 1 else f"#{seen_on_node}"
                    out.append(
                        {
                            "id": f"{_rel(root, path)}::{names.get(id(node), getattr(node, 'name', '?'))}{suffix}",
                            "reason": _decorator_reason(dec, consts),
                        }
                    )
    return out


def _skip_imperative_locations(tree_files: list[Path], root: Path) -> list[dict]:
    out = []
    for path in tree_files:
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError, OSError:
            continue
        consts = _module_str_constants(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _call_name(node.func) in (
                "pytest.skip",
                "_pytest.skipping.skip",
            ):
                reason = ""
                if node.args:
                    arg = node.args[0]
                    if isinstance(arg, ast.Constant):
                        reason = str(arg.value)
                    elif isinstance(arg, ast.Name):
                        reason = consts.get(arg.id, "")
                out.append({"id": f"{_rel(root, path)}:{node.lineno}", "reason": reason})
    return out


# it.skip("title", …) / test.skip(`title`, …) — the title is the stable key;
# a title-less call site falls back to line:column so two sites never collide.
_FRONTEND_SUPPRESSION_CALL_RE = re.compile(
    r"\.(skip|only|todo)\b\s*\(?\s*(?:`([^`]*)`|'([^']*)'|\"([^\"]*)\")?"
)


def _frontend_modifier_locations(root: Path) -> dict[str, list[dict]]:
    buckets: dict[str, list[dict]] = {"skip": [], "only": [], "todo": []}
    for path in _frontend_test_files(root):
        text = path.read_text()
        for m in _FRONTEND_SUPPRESSION_CALL_RE.finditer(text):
            kind, btick, s1, s2 = m.groups()
            title = next((t for t in (btick, s1, s2) if t is not None), None)
            line = text.count("\n", 0, m.start()) + 1
            col = m.start() - (text.rfind("\n", 0, m.start()) + 1) + 1
            ident = title if title else f"{line}:{col}"
            buckets[kind].append({"id": f"{_rel(root, path)}::{ident}", "reason": ""})
    return buckets


def _excluded_tree_locations(root: Path) -> list[dict]:
    text = (root / "scripts/validate.sh").read_text()
    names = set()
    for m in re.finditer(r"--ignore=(\S+)", text):
        tail = m.group(1).rstrip("\\").strip("'\"")
        parts = [p for p in tail.split("/") if p]
        if parts:
            names.add(parts[-1].rstrip("\\"))
    return [{"id": n, "reason": ""} for n in sorted(names)]


def _unspecced_patch_locations(root: Path) -> list[dict]:
    """WP4.2: convertible-but-unspecced mock-patch sites under
    backend/tests. The MEASURER is scripts/check-mock-spec.py (it owns the
    id minting and reuses autospec-sweep's classifier) -- the census only
    imports it, so gate and census can never disagree about the count."""
    import importlib.util

    gate = root / "scripts/check-mock-spec.py"
    if not gate.exists():
        # fixture trees (ratchet tests) carry no scripts/ copy — the MEASURER
        # is versioned code, not tree data; only what it walks (root/backend/
        # tests) comes from root.
        gate = Path(__file__).resolve().parent / "check-mock-spec.py"
    spec = importlib.util.spec_from_file_location("check_mock_spec_census_reuse", gate)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.sites_for_root(root)


def _coverage_omit_locations(root: Path) -> list[dict]:
    text = (root / "pyproject.toml").read_text()
    m = re.search(r"\[tool\.coverage\.run\].*?omit\s*=\s*\[(.*?)\]", text, re.DOTALL)
    if not m:
        return []
    entries = re.findall(r'"([^"]+)"', m.group(1))
    return [
        {"id": e, "reason": ""}
        for e in entries
        if "*" not in e
        and e != "backend/main.py"
        and e.startswith("backend/")
        and not e.startswith("backend/tests")
    ]


def locations(root: Path) -> dict[str, list[dict]]:
    """The full INVENTORY (WP1.2): every counted suppression, individually
    addressable. Count keys match census(); registry entries key on `id`."""
    backend_tests = sorted((root / "backend/tests").rglob("*.py"))
    fe = _frontend_modifier_locations(root)
    return {
        "collection_allowlist": _collection_allowlist_locations(root),
        "flake_allowlist": _flake_allowlist_locations(root),
        "frontend_quarantine": _frontend_quarantine_locations(root),
        "pytest_skip": _decorator_locations(backend_tests, root, "skip"),
        "pytest_skipif": _decorator_locations(backend_tests, root, "skipif"),
        "pytest_xfail": _decorator_locations(backend_tests, root, "xfail"),
        "pytest_skip_imperative": _skip_imperative_locations(backend_tests, root),
        "frontend_skip": fe["skip"],
        "frontend_only": fe["only"],
        "frontend_todo": fe["todo"],
        "excluded_test_trees": _excluded_tree_locations(root),
        "coverage_omit": _coverage_omit_locations(root),
        "unspecced_patch": _unspecced_patch_locations(root),
        "tpa_slow_list": _tpa_slow_list_locations(root),
    }


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
        "unspecced_patch": len(_unspecced_patch_locations(root)),
        "tpa_slow_list": len(_tpa_slow_list_locations(root)),
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
    parser.add_argument(
        "--locations",
        action="store_true",
        help="Emit the full inventory (category -> [{id, reason}]) instead of counts (WP1.2 registry key)",
    )
    args = parser.parse_args()

    if args.locations:
        print(json.dumps(locations(Path(args.root)), indent=2, sort_keys=True))
        return 0

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
