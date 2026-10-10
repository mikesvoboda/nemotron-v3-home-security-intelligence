#!/usr/bin/env python3
"""O2.3 (plan 01 §M1): which Python modules actually SHIP?

Walk imports from declared entry points and report which modules under
``backend/``, ``ai/`` and ``synthbench/`` are reachable. The model is
NAME-LEVEL, not package-level, and that is the whole point (00 §4.1):
``services/__init__.py`` imports 56 submodules and re-exports 274 names that
no production code imports, so a package-level walk calls the dead modules
live. The rules, each pinned by scripts/test_reachability.py:

* ``from pkg import name`` against a PACKAGE enters ``pkg/__init__.py`` (it
  does execute) but follows ONLY the re-export line that binds ``name`` —
  the __init__'s other import edges are dead. A package is thus shipped by
  the names production asks it for, not by what an interpreter that imported
  the whole tree would run.
* whole-module demands — ``import a.b``, ``importlib.import_module("a.b")``
  (via the allowlist), and ``from pkg import submodule`` (which auto-imports
  the submodule) — mark the target WHOLE, following all its module-level
  edges. The caller holds the namespace itself; its re-exports are the
  module's public surface. The real tree has zero namespace-package imports
  (measured at claim time), so this arm stays rare.
* TYPE_CHECKING-guarded imports do NOT ship (erased at runtime).
* function-level imports DO ship (they execute when the function runs).
* string / dynamic imports ship only through the ``entry_points.toml``
  allowlist; an un-allowlisted string literal is reported ``unresolved`` —
  never silently shipped, never silently dropped.

Tests (``test_*.py``, ``conftest.py``, anything under a ``tests/`` dir) are
never candidates: they leave with the modules they test. ``keep.toml`` ships
modules by declaration, one reason each.

Usage:
    uv run python scripts/reachability.py [--json out.json]
Exit 0 on a completed run. The Done-when verdict lives in the gate suite,
not this exit code.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
REPO_ROOT = _HERE.parent
DEFAULT_ENTRIES = _HERE / "reachability" / "entry_points.toml"
DEFAULT_KEEP = _HERE / "reachability" / "keep.toml"
DEFAULT_CANDIDATE_DIRS = ["backend", "ai", "synthbench"]

_EXCLUDED_PARTS = {"__pycache__", ".venv", "node_modules", ".mypy_cache"}


def _is_test_path(rel: str) -> bool:
    parts = rel.split("/")
    if parts[-1].startswith("test_") or parts[-1] == "conftest.py":
        return True
    return "tests" in parts[:-1]


def _module_dotted(rel: str) -> str:
    """pkg/mod.py -> pkg.mod; pkg/__init__.py -> pkg (it IS the package)."""
    stem = rel.removesuffix(".py")
    if stem.endswith("/__init__"):
        stem = stem[: -len("/__init__")]
    elif stem == "__init__":
        stem = ""
    return stem.replace("/", ".")


def _is_type_checking_test(test: ast.expr) -> bool:
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    if isinstance(test, ast.Attribute):
        return test.attr == "TYPE_CHECKING"
    return False


class ModuleView:
    """One candidate file's shipping edges, from its AST."""

    def __init__(self, rel: str, text: str) -> None:
        self.rel = rel
        self.lines = len(text.splitlines())
        self.dotted = _module_dotted(rel)
        # names bound by a top-level `from <target> import <name>` in THIS
        # file — the selective channel when this file is a package __init__:
        # name -> absolute target (relative resolved against this module).
        self.reexports: dict[str, str] = {}
        # whole-module demands this file makes at runtime: list of
        # (absolute target, demanded names or None-for-whole).
        self.demands: list[tuple[str, frozenset[str] | None]] = []
        # string-literal dynamic import targets (import_module / __import__).
        self.dynamic: list[str] = []
        self._parse_and_walk(text)

    # -- parsing ---------------------------------------------------------

    def _resolve_relative(self, level: int, module: str | None) -> str:
        """from . / ..x inside self -> absolute dotted target."""
        parts = self.dotted.split(".") if self.dotted else []
        if not self.rel.endswith("__init__.py"):
            # a plain module's package is its parent directory
            parts = parts[:-1]
        # level 1 = current package; level n walks up n-1 more
        base = parts[: len(parts) - (level - 1)] if level > 1 else parts
        joined = ".".join(base)
        if module:
            return f"{joined}.{module}" if joined else module
        # `from . import x` — each name is a submodule of the package itself;
        # handled by the caller via names-on-package; target IS the package.
        return joined

    def _parse_and_walk(self, text: str) -> None:
        tree = ast.parse(text, filename=self.rel)

        def record_from(node: ast.ImportFrom, toplevel: bool) -> None:
            if node.level:
                if node.module is None:
                    # `from . import x` / `from ..pkg import x` — each name is
                    # a submodule of the resolved package.
                    pkg = self._resolve_relative(node.level, None)
                    for alias in node.names:
                        sub = f"{pkg}.{alias.name}" if pkg else alias.name
                        if toplevel and alias.name != "*":
                            self.reexports[alias.asname or alias.name] = sub
                        if alias.name != "*":
                            self.demands.append((sub, None))
                    return
                target = self._resolve_relative(node.level, node.module)
            else:
                target = node.module or ""
            if not target:
                return
            if toplevel:
                for alias in node.names:
                    if alias.name != "*":
                        self.reexports[alias.asname or alias.name] = target
            names = frozenset(
                a.asname or a.name for a in node.names if a.name != "*"
            )
            self.demands.append((target, names or None))

        def scan_calls(stmt: ast.stmt) -> None:
            for sub in ast.walk(stmt):
                if not isinstance(sub, ast.Call):
                    continue
                fn = sub.func
                fname = (
                    fn.attr
                    if isinstance(fn, ast.Attribute)
                    else fn.id
                    if isinstance(fn, ast.Name)
                    else ""
                )
                if fname in ("import_module", "__import__") and sub.args:
                    first = sub.args[0]
                    if isinstance(first, ast.Constant) and isinstance(first.value, str):
                        self.dynamic.append(first.value)

        def visit_body(body: list[ast.stmt], toplevel: bool, in_tc: bool) -> None:
            for stmt in body:
                if isinstance(stmt, ast.Import):
                    scan_calls(stmt)
                    if in_tc:
                        continue
                    for alias in stmt.names:
                        # `import a.b` — whole-module demand on a.b.
                        self.demands.append((alias.name, None))
                    continue
                if isinstance(stmt, ast.ImportFrom):
                    scan_calls(stmt)
                    if in_tc:
                        continue
                    record_from(stmt, toplevel)
                    continue
                if isinstance(stmt, ast.Call):
                    scan_calls(stmt)
                    continue
                if isinstance(stmt, ast.If):
                    scan_calls(stmt)
                    tc = _is_type_checking_test(stmt.test)
                    visit_body(stmt.body, toplevel, in_tc or tc)
                    visit_body(stmt.orelse, toplevel, in_tc)
                    continue
                if isinstance(stmt, ast.Try):
                    scan_calls(stmt)
                    visit_body(stmt.body, toplevel, in_tc)
                    for handler in stmt.handlers:
                        visit_body(handler.body, toplevel, in_tc)
                    visit_body(stmt.orelse, toplevel, in_tc)
                    visit_body(stmt.finalbody, toplevel, in_tc)
                    continue
                if isinstance(stmt, ast.ClassDef):
                    scan_calls(stmt)
                    visit_body(stmt.body, toplevel, in_tc)  # class body: import time
                    continue
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    scan_calls(stmt)  # decorators/defaults run at def time
                    visit_body(stmt.body, False, in_tc)
                    continue
                # anything else (with/for/while/async with/...) — descend,
                # keeping the import-time context, and catch embedded calls.
                scan_calls(stmt)
                for field in getattr(stmt, "_fields", ()):
                    child = getattr(stmt, field)
                    if isinstance(child, list) and all(isinstance(c, ast.stmt) for c in child):
                        visit_body(child, toplevel, in_tc)  # type: ignore[arg-type]

        visit_body(tree.body, toplevel=True, in_tc=False)


def _discover_candidates(root: Path, candidate_dirs: list[str]) -> dict[str, ModuleView]:
    """Every non-test .py under the candidate dirs, parsed. Empty files are
    not candidates (an empty __init__ ships nothing and hides nothing)."""
    views: dict[str, ModuleView] = {}
    for d in candidate_dirs:
        base = root / d
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.py")):
            rel = p.relative_to(root).as_posix()
            if any(part in _EXCLUDED_PARTS for part in p.parts):
                continue
            if _is_test_path(rel):
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            if not text.strip():
                continue
            views[rel] = ModuleView(rel, text)
    return views


def analyze(
    root: Path,
    *,
    entries: list[str],
    candidate_dirs: list[str],
    keep: list[str],
    dynamic_allow: list[str],
) -> dict[str, Any]:
    root = Path(root)
    views = _discover_candidates(root, candidate_dirs)
    by_dotted = {v.dotted: v for v in views.values()}

    live: set[str] = set()
    unresolved: list[dict[str, str]] = []
    entry_missing: list[str] = []

    dyn_seen: set[tuple[str, str]] = set()

    first_roots = {d.rstrip("/") for d in candidate_dirs}

    def run_dynamic(rel: str, view: ModuleView) -> bool:
        """Apply a live module's string-imports; True if anything new shipped."""
        grew = False
        for lit in view.dynamic:
            if (rel, lit) in dyn_seen:
                continue
            dyn_seen.add((rel, lit))
            if lit not in dynamic_allow:
                # A literal rooted OUTSIDE the candidate trees (stdlib, a
                # third-party package) carries no candidate edge by
                # construction — reporting it would be permanent noise that
                # trains everyone to ignore the unresolved list. Only a
                # first-party literal that isn't allowlisted is a finding.
                if lit.split(".", 1)[0] in first_roots:
                    unresolved.append({"module": rel, "target": lit})
                continue
            before = len(live)
            demand(lit, None, rel)
            grew = grew or len(live) > before
        return grew

    def demand(target: str, names: frozenset[str] | None, site: str) -> None:
        """Ship `target` for the given names (None = whole module)."""
        work: list[tuple[str, frozenset[str] | None]] = [(target, names)]
        seen: set[tuple[str, frozenset[str] | None]] = set()
        fresh: list[tuple[str, ModuleView]] = []
        while work:
            tgt, ns = item = work.pop()
            if item in seen:
                continue
            seen.add(item)
            view = by_dotted.get(tgt)
            if view is None:
                continue
            # Selectivity is a package-__init__ concept only: asking ANY name
            # out of a plain module executes that whole module, so every edge
            # it holds ships. A package asked for NAMES ships only through the
            # lines binding those names (the §M1 rule); a package demanded
            # WHOLE (import a.b) ships its namespace — all edges.
            whole = ns is None or not view.rel.endswith("__init__.py")
            first = view.rel not in live
            live.add(view.rel)
            if first:
                fresh.append((view.rel, view))
            if whole or ns is None:
                work.extend(view.demands)
            else:
                for n in ns:
                    if n in view.reexports:
                        # selective channel: follow ONLY this binding's line.
                        work.append((view.reexports[n], frozenset({n})))
                    elif f"{tgt}.{n}" in by_dotted:
                        # `from pkg import submodule` — auto-imports whole.
                        work.append((f"{tgt}.{n}", None))
                    # else: a name the package binds in place (or not at all)
                    # — no import edge to follow.
        for rel, view in fresh:
            if run_dynamic(rel, view):
                # a newly-allowed literal shipped new modules whose own
                # literals must be examined too: demand() already queued
                # them via fresh, and the outer while-loop below sweeps.
                pass

    for entry in entries:
        if not (root / entry).is_file():
            entry_missing.append(entry)
            continue
        view = ModuleView(
            entry, (root / entry).read_text(encoding="utf-8", errors="replace")
        )
        live.add(entry)
        for target, ns in view.demands:
            demand(target, ns, entry)
        run_dynamic(entry, view)

    # Entry files are not in `views` (entries may sit outside the candidate
    # walk's parse set — they don't); every candidate that went live had its
    # literals applied inside demand() via fresh. One sweep catches any that
    # shipped without passing through a fresh mark (whole-demands reuse).
    changed = True
    while changed:
        changed = False
        for rel in list(live):
            swept = views.get(rel)
            if swept is not None and run_dynamic(rel, swept):
                changed = True

    # keep list: ship by declaration; a pattern matching nothing is NOT a hit.
    keep_hits: list[str] = []
    for pattern in keep:
        prefix = pattern.rstrip("/")
        hit = False
        for rel in views:
            stem = rel.removesuffix(".py")
            if stem == prefix or stem.startswith(prefix + "/"):
                live.add(rel)
                hit = True
        for suffix in (".py", "/__init__.py"):
            direct = f"{prefix}{suffix}"
            if (root / direct).is_file() and not _is_test_path(direct):
                live.add(direct)
                hit = True
        if hit:
            keep_hits.append(pattern)

    not_shipping = sorted(
        ({"module": rel, "lines": v.lines} for rel, v in views.items() if rel not in live),
        key=lambda r: str(r["module"]),
    )
    return {
        "shipping": sorted(live),
        "not_shipping": not_shipping,
        "keep_hits": keep_hits,
        "unresolved": sorted(unresolved, key=lambda d: (d["module"], d["target"])),
        "entry_missing": entry_missing,
    }


def _read_toml(path: Path) -> dict[str, Any]:
    # CLI-reachable path: resolve + require a real file before reading
    # (the ratchet-check.py pattern for the semgrep path-traversal rule).
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise SystemExit(f"reachability: config file not found: {resolved}")
    return tomllib.loads(resolved.read_text(encoding="utf-8"))


def load_entry_points(path: Path) -> tuple[list[str], list[str]]:
    data = _read_toml(path)
    entries = [str(e) for e in data.get("entries", [])]
    allow = [str(a) for a in data.get("dynamic_allow", [])]
    return entries, allow


def load_keep(path: Path) -> list[str]:
    data = _read_toml(path)
    out = []
    for row in data.get("keep", []):
        out.append(str(row["module"]))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--entries", type=Path, default=DEFAULT_ENTRIES)
    ap.add_argument("--keep", type=Path, default=DEFAULT_KEEP)
    ap.add_argument("--json", type=Path, default=None, help="write full output JSON")
    args = ap.parse_args(argv)

    entries, allow = load_entry_points(args.entries)
    keep = load_keep(args.keep)
    out = analyze(
        REPO_ROOT,
        entries=entries,
        candidate_dirs=DEFAULT_CANDIDATE_DIRS,
        keep=keep,
        dynamic_allow=allow,
    )
    dead_lines = sum(m["lines"] for m in out["not_shipping"])
    print(
        f"shipping={len(out['shipping'])}  non-shipping={len(out['not_shipping'])} "
        f"({dead_lines} lines)  keep-hits={len(out['keep_hits'])}  "
        f"unresolved={len(out['unresolved'])}  entry-missing={len(out['entry_missing'])}"
    )
    for u in out["unresolved"]:
        print(f"  unresolved dynamic import: {u['module']} -> {u['target']}", file=sys.stderr)
    for e in out["entry_missing"]:
        print(f"  declared entry point missing: {e}", file=sys.stderr)
    if args.json:
        args.json.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
