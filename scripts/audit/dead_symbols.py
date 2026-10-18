#!/usr/bin/env python3
"""Dead-symbol census (B3.3 box 3): exception classes and metrics nobody calls.

``00-audit.md`` §4.1 states the counts -- "11 unused exception classes", and the R8
residue line's "delete the uncalled metrics" -- but names no symbol. This script is
the scan view those counts must be re-measured under, so the deletions have a named
list to work from and the next reviewer has an instrument to re-run rather than a
prose number to trust.

Why a naive whole-word count is wrong here (each of these fired while writing this):

* Duplicate class names. ``ValidationError`` is declared in BOTH
  ``api/middleware/error_handler.py`` and ``core/exceptions.py``, and the two are
  indistinguishable to an unbound name reference, so resolving which one a given
  ``raise`` means would need import-and-scope analysis this census deliberately does
  not do. Rather than guess, references are UNIONED by name: if EITHER declaration is
  referenced, NEITHER is reported unused. That over-counts LIVE, which the
  scripts/audit/AGENTS.md doctrine allows ("a census may over-count LIVE (safe)") and
  it is why ``unused`` here is a floor, never a ceiling -- a name duplicated anywhere
  in the tree is invisible to it.
* Base-class handling. ``except AppException`` catches every subclass without naming
  it, so a subclass with no NAMED handler is not therefore unreachable -- it is only
  unreachable with no raiser. The verdict below claims no more than "no reference of
  any kind exists", which is the safe half of that.
* Barrel re-exports. §4.1's own finding is that ``services/__init__.py`` re-exports
  274 names nobody imports, which HIDES dead modules from a package-level scan. So an
  occurrence that is only a ``from x import Y`` alias or an ``__all__`` string is
  counted as a re-export, never as a use -- otherwise the barrel keeps itself alive.
* Dynamic references. A name reached through ``globals()["Foo"]``, a dict key or a
  ``getattr`` string is live without being a ``Name`` node. Registration here is
  static (``main.py`` calls ``register_exception_handlers``; the error handler has no
  ``__subclasses__``/``vars()`` walk -- verified), but the census still records
  string-keyed references as ``dynamic`` and refuses to call such a symbol dead.
* Dashboards are consumers. A metric with no Python caller is LIVE if a Grafana panel
  or a Prometheus rule queries its name, so ``monitoring/`` is a second corpus.
  Histograms are queried by their SUFFIXED names (``_bucket``, ``_sum``, ``_count``,
  ``_total``), so those variants are searched too -- the falsified
  ``backend/AGENTS.md:248`` claim ("the dashboards query them") survived precisely
  because nobody had checked the name itself against the corpus.
* Docstrings are not uses. Prose naming a symbol (as this file's own R8 quotation
  does) must not count as a reference, so docstring constants are excluded.

Tests count as evidence AGAINST deletion here (unlike the settings-orphan census,
which asks a different question: "read outside config.py"). Deleting a symbol a test
names means editing that test in the same PR, so the ``prod_dead`` tier keeps the work
visible instead of hiding it inside ``unused``.

Known limit, stated rather than assumed: metric DECLARATIONS are found by the
``NAME = Counter("hsi_x", ...)`` assignment form. A metric built through a helper
factory would be missed here -- the same form the ``git grep`` definition survey used,
so the two agree, but a new helper would silently shrink this census.

Verdicts:
  unused      no live reference, no dynamic reference, no use outside its own file
  prod_dead   referenced only from tests
  reexported  referenced only through barrel imports / ``__all__``
  queried     (metrics) a dashboard or alert rule names it -- live without a caller
  live        referenced from production code

Run:    uv run python scripts/audit/dead_symbols.py [--root REPO] [--tier unused] [--kind exception]
Test:   uv run python -m pytest scripts/audit/test_dead_symbols.py -q
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# prometheus_client metric constructors recognised as metric definitions.
METRIC_FACTORIES = {"Counter", "Histogram", "Gauge", "Info", "Enum", "Summary"}
# prometheus_client appends these to the registered name for some metric types; a
# dashboard queries the suffixed name, so a suffix hit counts as a query hit.
METRIC_QUERY_SUFFIXES = ("", "_total", "_sum", "_count", "_bucket", "_created")
EXCEPTION_ROOTS = {"Exception", "BaseException"}
EXCEPTION_SUFFIXES = ("Error", "Exception", "Failure")
PY_SUFFIXES = (".py", ".pyi")
# functions that can reach a symbol through a string argument
STRING_ACCESSORS = {"getattr", "setattr", "hasattr", "delattr", "import_module"}


@dataclass
class Declaration:
    kind: str             # "exception" | "metric"
    name: str             # the python-bound name
    path: str
    lineno: int
    registered: str = ""  # metrics: the prometheus name string
    bases: list[str] = field(default_factory=list)

    @property
    def declared_at(self) -> str:
        return f"{self.path}:{self.lineno}"


@dataclass
class FileIndex:
    """One pass over one file: every way it can mention a symbol, keyed by name."""

    rel: str
    names: dict[str, list[str]] = field(default_factory=dict)      # Name nodes (real reads)
    attrs: dict[str, list[str]] = field(default_factory=dict)      # Attribute tails (.name)
    handlers: dict[str, list[str]] = field(default_factory=dict)   # except-clause mentions
    reexport: dict[str, list[str]] = field(default_factory=dict)   # import aliases, __all__
    dynamic: dict[str, list[str]] = field(default_factory=dict)    # string-keyed access
    is_test: bool = False


def is_test_path(path: str) -> bool:
    parts = path.split("/")
    return "tests" in parts or Path(path).stem.startswith("test_")


def tracked_files(root: Path) -> list[str]:
    """Tracked files, so venvs, node_modules and build junk are never parsed."""
    try:
        out = subprocess.run(  # intentional - runs git, fixed argv list
            ["git", "ls-files", "-z"],
            cwd=root,
            capture_output=True,
            check=True,
            text=True,
            timeout=120,
        ).stdout
    except Exception as exc:  # fall back to a walk, loudly
        print(f"[WARN] git ls-files failed ({exc}); walking the tree instead", file=sys.stderr)
        return [
            str(p.relative_to(root))
            for p in root.rglob("*")
            if p.is_file() and ".git" not in p.parts and ".venv" not in p.parts
        ]
    return [p for p in out.split("\0") if p]


def _docstring_ids(tree: ast.Module) -> set[int]:
    """id() of every Constant that is a docstring, so prose never counts as a use."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            if ast.get_docstring(node):  # type: ignore[arg-type]
                body = getattr(node, "body", [])
                if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                    ids.add(id(body[0].value))
    return ids


def index_file(rel: str, tree: ast.Module) -> FileIndex:
    """Single walk: build the file's symbol-mention index."""
    idx = FileIndex(rel=rel, is_test=is_test_path(rel))
    docs = _docstring_ids(tree)
    bind_sites: set[tuple[int, int]] = set()

    def add(bucket: dict[str, list[str]], key: str, node: ast.AST) -> None:
        if key:
            bucket.setdefault(key, []).append(f"{rel}:{getattr(node, 'lineno', 0)}")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import | ast.ImportFrom):
            for alias in node.names:
                bind_sites.add((alias.lineno or node.lineno, alias.col_offset or node.col_offset))
                add(idx.reexport, alias.asname or alias.name.split(".")[0], node)
        elif isinstance(node, ast.Name):
            # Load only: `HSI_FOO = Counter(...)` and `global HSI_FOO` are writes, and
            # counting the assignment would make every never-observed metric live at
            # its own definition site -- the exact symbol this census is looking for.
            if not isinstance(node.ctx, ast.Load) or (node.lineno, node.col_offset) in bind_sites:
                continue
            add(idx.names, node.id, node)
        elif isinstance(node, ast.Attribute):
            add(idx.attrs, node.attr, node)
        elif isinstance(node, ast.ExceptHandler) and node.type is not None:
            for sub in ast.walk(node.type):
                if isinstance(sub, ast.Name):
                    add(idx.handlers, sub.id, node)
                elif isinstance(sub, ast.Attribute):
                    add(idx.handlers, sub.attr, node)
        elif isinstance(node, ast.ClassDef):
            for base in node.bases:  # a base mention is a use, not a re-export
                for sub in ast.walk(base):
                    if isinstance(sub, ast.Name):
                        add(idx.names, sub.id, node)
                    elif isinstance(sub, ast.Attribute):
                        add(idx.attrs, sub.attr, node)
        elif isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets
        ):
            for const in ast.walk(node.value):
                if isinstance(const, ast.Constant) and isinstance(const.value, str):
                    add(idx.reexport, const.value, const)
        elif isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str) and id(key) not in docs:
                    add(idx.dynamic, key.value, node)
        elif isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
            if isinstance(node.slice.value, str) and id(node.slice) not in docs:
                add(idx.dynamic, node.slice.value, node)
        elif isinstance(node, ast.Call):
            fname = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            if fname in STRING_ACCESSORS or fname in {"get", "pop", "setdefault"}:
                for arg in node.args[1:] if fname in STRING_ACCESSORS else node.args[1:2]:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        add(idx.dynamic, arg.value, node)
    return idx


# --------------------------------------------------------------------------- #
# declarations
# --------------------------------------------------------------------------- #
def base_name(node: ast.expr) -> str:
    """The written name of a base class: `Foo`, `a.b.Foo`, `Foo[T]` -> `Foo`."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        return base_name(node.value)
    if isinstance(node, ast.Call):
        return base_name(node.func)
    return ""


def exception_declarations(trees: dict[str, ast.Module]) -> list[Declaration]:
    """Every class that closes over Exception/BaseException, by name-suffix or base."""
    parents: dict[str, set[str]] = {}
    for tree in trees.values():
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                parents.setdefault(node.name, set()).update(base_name(b) for b in node.bases if base_name(b))

    memo: dict[str, bool] = {}

    def closes_over(name: str, seen: frozenset[str] = frozenset()) -> bool:
        if name in EXCEPTION_ROOTS:
            return True
        if not name or name in seen:
            return False  # pathological self-reference is not exception evidence
        if name in memo and not seen:
            return memo[name]
        result = any(closes_over(p, seen | {name}) for p in parents.get(name, ()))
        if not seen:
            memo[name] = result
        return result

    decls: list[Declaration] = []
    for rel, tree in trees.items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            bases = [base_name(b) for b in node.bases]
            is_exception = any(closes_over(b) for b in bases)
            # The name-suffix rule alone is wrong the same way the metric factory
            # match was: pytest COLLECTS classes named Test*, so a test body named
            # `class TestRateLimitError:` (no bases at all) is not an exception class.
            named = node.name.endswith(EXCEPTION_SUFFIXES) and not node.name.startswith("Test")
            if not (named or is_exception):
                continue
            decls.append(
                Declaration(
                    kind="exception", name=node.name, path=rel, lineno=node.lineno or 0, bases=bases
                )
            )
    return decls


def prometheus_factory_names(tree: ast.Module) -> set[str]:
    """Which names in this file are prometheus_client metric constructors.

    Name-matching the factory alone is wrong and was measured wrong: ``Summary`` is
    BOTH a prometheus_client type and this repo's own ``models.summary.Summary``, so
    matching by name called ``latest_hourly = Summary(...)`` a metric declaration.
    Each candidate's ORIGIN is resolved per file instead: names bound by
    ``from prometheus_client import Counter`` (or an alias of one), and any module
    alias introduced by ``import prometheus_client [as X]`` -- qualified
    ``prometheus_client.Counter(...)`` calls are matched by that alias or by the
    literal module name.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "prometheus_client":
            for alias in node.names:
                if alias.name in METRIC_FACTORIES:
                    names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] != "prometheus_client":
                    continue
                if alias.asname:
                    names.add(alias.asname)
                else:
                    names.add(alias.name.split(".")[0])
    return names


def metric_declarations(trees: dict[str, ast.Module]) -> list[Declaration]:
    decls: list[Declaration] = []
    for rel, tree in trees.items():
        bound_names = prometheus_factory_names(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            call = node.value
            if not isinstance(target, ast.Name) or not isinstance(call, ast.Call):
                continue
            if isinstance(call.func, ast.Attribute):
                # a qualified call: the holder module must BE prometheus_client (or a
                # bound alias of it) for the factory name to mean a metric type
                holder = getattr(call.func.value, "id", "")
                factory = call.func.attr
                ok = factory in METRIC_FACTORIES and (
                    holder == "prometheus_client" or holder in bound_names
                )
                if not ok:
                    continue
            else:
                factory = getattr(call.func, "id", "")
                # a bare Counter(...) counts only if THIS file imported it from
                # prometheus_client -- the fix for the app's own Summary class
                if factory not in METRIC_FACTORIES or factory not in bound_names:
                    continue
            registered = ""
            if call.args and isinstance(call.args[0], ast.Constant):
                registered = str(call.args[0].value)
            else:
                for kw in call.keywords:
                    if kw.arg in {"name", "namespace", "subsystem"} and isinstance(kw.value, ast.Constant):
                        registered = str(kw.value.value)
                        break
            decls.append(
                Declaration(
                    kind="metric",
                    name=target.id,
                    path=rel,
                    lineno=node.lineno or 0,
                    registered=registered or target.id,
                )
            )
    return decls


# --------------------------------------------------------------------------- #
# monitoring corpus (dashboards + alerting rules are metric consumers)
# --------------------------------------------------------------------------- #
def monitoring_corpus(root: Path, relpaths: list[str]) -> dict[str, str]:
    corpus: dict[str, str] = {}
    for rel in relpaths:
        if not rel.startswith("monitoring/") or rel.endswith("/AGENTS.md"):
            continue  # AGENTS.md is prose about monitoring, not a query
        if not rel.endswith((".json", ".yml", ".yaml", ".rules", ".txt")):
            continue
        try:
            corpus[rel] = (root / rel).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"[WARN] unreadable {rel}: {exc}", file=sys.stderr)
    return corpus


def query_hits(corpus: dict[str, str], metric: Declaration) -> list[str]:
    """Does any dashboard panel or alert rule query this metric's name?"""
    hits: list[str] = []
    for rel, text in corpus.items():
        lowered = text.lower()
        for suffix in METRIC_QUERY_SUFFIXES:
            candidate = (metric.registered + suffix).lower()
            if candidate and re.search(rf"(?<![\w.]){re.escape(candidate)}(?![\w])", lowered):
                hits.append(rel)
                break
    return hits


# --------------------------------------------------------------------------- #
# verdicts
# --------------------------------------------------------------------------- #
def collect(name: str, decl: Declaration, indexes: dict[str, FileIndex]) -> dict[str, list[str]]:
    live: list[str] = []
    tests: list[str] = []
    reexport: list[str] = []
    dynamic: list[str] = []
    for idx in indexes.values():
        seen: set[str] = set()
        for bucket, sink in (
            (idx.names, tests if idx.is_test else live),
            (idx.attrs, tests if idx.is_test else live),
            (idx.handlers, tests if idx.is_test else live),
            (idx.reexport, reexport),
            (idx.dynamic, dynamic),
        ):
            for loc in bucket.get(name, ()):
                if loc not in seen:
                    seen.add(loc)
                    sink.append(loc)
    # the declaration site itself is not a use of the symbol
    live = [loc for loc in live if loc != decl.declared_at]
    return {"live": live, "test": tests, "reexport": reexport, "dynamic": dynamic}


def verdict(decl: Declaration, refs: dict[str, list[str]], queries: list[str]) -> str:
    other_live = [r for r in refs["live"] if not r.startswith(decl.path + ":")]
    same_file = [r for r in refs["live"] if r.startswith(decl.path + ":")]
    other_tests = [r for r in refs["test"] if not r.startswith(decl.path + ":")]
    if queries:
        return "queried"      # a dashboard/rule reads it: live without a caller
    if refs["dynamic"] or other_live or same_file:
        return "live"         # dynamic reach is treated as live: the safe direction
    if other_tests:
        return "prod_dead"    # only tests name it -- deleting means editing those too
    if refs["reexport"]:
        return "reexported"   # alive only in a barrel: §4.1's own hiding mechanism
    return "unused"


def scan(root: Path) -> dict:
    files = tracked_files(root)
    trees: dict[str, ast.Module] = {}
    for rel in files:
        if not rel.endswith(PY_SUFFIXES):
            continue
        try:
            trees[rel] = ast.parse((root / rel).read_text(encoding="utf-8", errors="replace"), rel, "exec")
        except (SyntaxError, UnicodeDecodeError, OSError, ValueError) as exc:
            print(f"[WARN] unparseable {rel}: {exc}", file=sys.stderr)
    indexes = {rel: index_file(rel, tree) for rel, tree in trees.items()}
    corpus = monitoring_corpus(root, files)

    rows: list[dict] = []
    for decl in exception_declarations(trees) + metric_declarations(trees):
        refs = collect(decl.name, decl, indexes)
        queries = query_hits(corpus, decl) if decl.kind == "metric" else []
        rows.append(
            {
                "kind": decl.kind,
                "name": decl.name,
                "declared_at": decl.declared_at,
                "declared_in_tests": is_test_path(decl.path),
                "bases": decl.bases,
                "registered": decl.registered,
                "verdict": verdict(decl, refs, queries),
                "live_refs": sorted(set(refs["live"]))[:12],
                "live_ref_count": len(refs["live"]),
                "test_refs": sorted(set(refs["test"]))[:12],
                "reexported_via": sorted({r.split(":")[0] for r in refs["reexport"]})[:8],
                "dynamic_refs": sorted(set(refs["dynamic"]))[:8],
                "query_files": queries,
            }
        )
    rows.sort(key=lambda r: (r["verdict"] != "unused", r["verdict"] != "prod_dead", r["kind"], r["name"]))
    counts: dict[str, dict[str, int]] = {}
    for row in rows:
        counts.setdefault(row["kind"], {}).setdefault(row["verdict"], 0)
        counts[row["kind"]][row["verdict"]] += 1
    return {
        "files_scanned": len(files),
        "python_files_parsed": len(trees),
        "monitoring_files": len(corpus),
        "totals": counts,
        "symbols": rows,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    ap.add_argument("--tier", default="", help="only report this verdict (unused, prod_dead, ...)")
    ap.add_argument("--kind", default="", help="only report this kind (exception, metric)")
    args = ap.parse_args(argv)
    if not args.root.is_dir():
        print(f"[ERROR] --root {args.root} is not a directory", file=sys.stderr)
        return 1
    result = scan(args.root)
    if args.kind or args.tier:
        result["symbols"] = [
            r
            for r in result["symbols"]
            if (not args.kind or r["kind"] == args.kind) and (not args.tier or r["verdict"] == args.tier)
        ]
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    print(file=sys.stdout)
    for kind, tally in sorted(result["totals"].items()):
        print(f"{kind}: " + ", ".join(f"{n} {v}" for n, v in sorted(tally.items())), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
