#!/usr/bin/env python3
"""Backend change -> test selection for validate.sh --fast (spec SS4.1).

Mechanism (ruling recorded in the plan, Task 10): dotted-reference truth from
the test files' own text, not a path-mirroring table. One regex over each test
file captures every `backend.a.b.c` mention, which uniformly covers top-level
imports, function-local (lazy) imports, and mock patch strings - the three
forms the fact-sweep found, with the lazy/patch forms being exactly what
filename or top-level-AST heuristics silently miss.

Directory policy: any change under backend/api/** adds backend/tests/contracts
(the smoke tier - route wiring / OpenAPI shape break class). Spec-text ruling
(plan Task 10): the spec's "3 smoke files named in validate.sh's contracts
step" do not exist on disk (validate.sh has no contracts step - grep 'contracts'
scripts/validate.sh returns comment-only hits), so the smoke set IS
backend/tests/contracts/ (the CI-named contracts tier; the draft-era set
included test_schemathesis_contracts, a zero-test stub since DELETED
2026-09-16 under R-M2-COLLECTION-FINDINGS' queued revive-or-delete).
Policy contributions must DEFINE tests: the fast tier is a gate and
fast-backend-runner detector 1 CANNOT-RUNs a zero-test file - pinned by
scripts/test_fast_select.py::test_contract_policy_files_define_tests.

Usage: fast_select.py --base REF [--list-out FILE] [--why]
Stdout: human report ending in machine lines:
  SELECTED-BACKEND-FILES: N
Exit: 0 report produced (selection may be empty), 2 git failure.

Inert-additive (M1 constraint): scripts/ is outside pytest testpaths; the
paired scripts/test_fast_select.py is not collected by validate.sh until the
--fast tier lands. The regex also catches prose/docstrings mentioning dotted
paths - over-selection direction only, and WP2.1 promoted the advisory
selector to a GATE: there, over-selection is NOT harmless (the WP2.3
manifest runs everything selected and names what cannot run).
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REF_RE = re.compile(r"backend(?:\.[A-Za-z_][A-Za-z0-9_]*)+")
API_POLICY_DIR = "backend/api/"
SMOKE_GLOB = "backend/tests/contracts"


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        print(f"git {' '.join(args)} failed: {proc.stderr.strip()}", file=sys.stderr)
        raise SystemExit(2)
    return proc.stdout


def changed_files(root: Path, base: str) -> list[str]:
    # Tracked diff (renames/deletions surface through git's own filter) plus
    # untracked-not-ignored files, so an unsaved new test still selects.
    files = set(git(root, "diff", "--name-only", base).splitlines())
    files |= set(git(root, "ls-files", "--others", "--exclude-standard").splitlines())
    return sorted(files)


def module_of(rel: str) -> str | None:
    """backend/services/alert_service.py -> backend.services.alert_service.

    A package __init__ normalises to the PACKAGE name, not `pkg.__init__`:
    the importable dotted name of backend/api/__init__.py IS backend.api, and
    tests reference it as such. Leaving the .__init__ suffix would (a) make a
    changed __init__ match no test reference (referrers' prefix is
    `backend.api.__init__.`, which never prefix-matches a `backend.api` test
    reference) and (b) mis-root relative-import resolution in the closure
    (pkg must be the package, not the __init__ module).
    """
    if not rel.endswith(".py") or not rel.startswith("backend/"):
        return None
    if rel.endswith("/__init__.py"):
        rel = rel[: -len("/__init__.py")]
    else:
        rel = rel[: -len(".py")]
    return rel.replace("/", ".")


def test_files(root: Path) -> list[str]:
    out = git(root, "ls-files", "-z", "backend/tests").split("\0")
    return [f for f in out if Path(f).name.startswith("test_") and f.endswith(".py")]


def dotted_refs(root: Path, rel_test: str) -> set[str]:
    try:
        text = (root / rel_test).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    return set(REF_RE.findall(text))


PRODUCER_CACHE: dict[str, dict[str, set[str]]] = {}


def scan_modules(root: Path) -> dict[str, set[str]]:
    """dotted module -> set of dotted names it PRODUCES (imports).

    Two edge sources, both needed (WP2.2 measurements, ledger):
      - REF_RE text scan catches `from backend.api.metrics import x` and any
        deeper dotted mention (58ms over the full 536-file production tree)
      - AST ImportFrom(level>0) catches `from .sibling import x` — production
        has 54 files / 336 relative-import statements, tests have ZERO, so
        relative edges exist ONLY on the production side of the graph, which
        is exactly where transitivity lives (fixture: alerts.py's
        `from .alert_service import ...` is the untouched intermediate).
    Cycle-safe by construction: the graph is data; the BFS below caps depth.
    """
    # Producer graph = PRODUCTION files + conftest.py. Tests are attached by
    # referrers() at the end (their dotted refs, the shipped mechanism), so
    # scanning the ~1100 test files here is pure cost — and including them
    # would let a test file act as an intermediate, selecting other tests
    # through it (test-to-test selection is not what any tier promises).
    # conftest.py is the ONE backend/tests/ exception, and not an accident:
    # pytest never collects a conftest as a test, so a conftest node can
    # carry edges but can never be SELECTED (referrers/index only contain
    # test_*.py). Its text-scan sees the fixture's FUNCTION-LOCAL imports
    # (unit/conftest.py:136 `from backend.main import app`), which is how
    # fixture-indirect tests reach the app (rebench miss: test_rum reaches
    # a middleware fault through the shared client fixture; the production
    # graph alone cannot see the last hop).
    out: dict[str, set[str]] = {}
    rels = git(root, "ls-files", "-z", "backend").split("\0")
    for rel in (
        r
        for r in rels
        if r.endswith(".py")
        and (not r.startswith("backend/tests/") or Path(r).name == "conftest.py")
    ):
        mod = module_of(rel)
        if mod is None:
            continue
        try:
            text = (root / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        edges: set[str] = set(REF_RE.findall(text))
        # relative-import edges: level L + (optional module) resolved against
        # this file's package. `from . import y` in backend/services/alerts.py
        # (package backend.services) -> backend.services.y (module or pkg);
        # `from .x import z` -> backend.services.x. AST only where a relative
        # import exists (54/536 production files) — full-tree ast.parse was
        # ~4.4s of the measured 4.7s scan; the prefilter drops it to ~0.4s.
        if "from ." not in text and "import ." not in text:
            out[mod] = edges
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            tree = None
        if tree is not None:
            pkg = mod if rel.endswith("__init__.py") else mod.rpartition(".")[0]
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.level:
                    base = pkg
                    for _ in range(node.level - 1):
                        base = base.rpartition(".")[0]
                    if node.module:
                        target = f"{base}.{node.module}" if base else node.module
                        edges.add(target)
                    else:
                        # `from . import y`: the PACKAGE executes at import
                        # time (its __init__), and each named sibling may be
                        # a submodule — record both edges (attribute-vs-module
                        # ambiguity is safe: unknown names are dead ends in
                        # the inverted graph, prefix lookup keeps precision).
                        if base:
                            edges.add(base)
                        for a in node.names:
                            if base:
                                edges.add(f"{base}.{a.name}")
        out[mod] = edges
    return out


def producers_of(root: Path) -> dict[str, set[str]]:
    """module -> modules that import it (invert scan_modules)."""
    key = str(root.resolve())
    if key not in PRODUCER_CACHE:
        fwd = scan_modules(root)
        inv: dict[str, set[str]] = defaultdict(set)
        for src, edges in fwd.items():
            for e in edges:
                inv[e].add(src)
        PRODUCER_CACHE[key] = inv
    return PRODUCER_CACHE[key]


def closure(root: Path, seeds: set[str], max_depth: int = 4) -> dict[str, tuple[int, str]]:
    """All modules transitively IMPORTING any seed (the WP2.2 mechanism).

    Direction: producers of the changed module (who imports it), then their
    producers, ... Depth-capped (default 4) and visited-set cycle-safe. The
    cap is a honesty knob, not a correctness one — a real import chain deeper
    than 4 to a test-reachable module is rare enough that capping beats an
    unbounded walk on a 536-module graph for wall-clock; misses below the cap
    stay visible via UNMAPPED/referrers accounting.

    Returns module -> (depth, nearest-seed) for --why chains.
    """
    inv = producers_of(root)
    seen: dict[str, tuple[int, str]] = {s: (0, s) for s in seeds}
    frontier = set(seeds)
    for depth in range(1, max_depth + 1):
        nxt: dict[str, str] = {}  # newcomer -> the frontier module it imports
        for m in frontier:
            # Two prefix directions, both load-bearing (fixture-proven):
            #  - edge `m.deeper`: an attribute capture (`backend.api.metrics.foo`)
            #    must light up producers of module m (referrers() semantics).
            #  - edge a PACKAGE prefix of m: `from backend.api import x`
            #    stores edge `backend.api` (the bare package — attribute-vs-
            #    submodule is unresolvable textually); a change to module m
            #    inside that package must reach that importer too. This is
            #    the bake-off's class: test_websocket_timeout-style imports of
            #    a package/symbol while the changed module lives inside it.
            for name, prods in inv.items():
                if name == m or name.startswith(m + ".") or m.startswith(name + "."):
                    for p in prods:
                        if p not in seen:
                            nxt.setdefault(p, m)
        if not nxt:
            break
        # nxt[m]'s target is always a frontier module already in seen, so one
        # hop reaches its seed label
        for m, via in nxt.items():
            seen[m] = (depth, seen[via][1])
        frontier = set(nxt)
    return seen


def referrers(index: dict[str, list[str]], dotted: str) -> set[str]:
    """Tests referencing the module `dotted` exactly OR via a deeper path.

    Patch targets and lazy attribute access are dotted deeper than the module
    (`patch("backend.api.routes.metrics.get_x")` for a change to metrics.py),
    so lookup must be prefix-aware — exact-match alone (the plan's Step-3
    listing) fails its own Task-10 patch-string test, caught by the draft
    logic smoke. Prefix matching also keeps package-__init__ changes pulling
    submodule references: the over-selection direction, which is the safe one
    for an advisory tier.
    """
    hits = set(index.get(dotted, []))
    prefix = dotted + "."
    for key, tests in index.items():
        if key.startswith(prefix):
            hits.update(tests)
    return hits


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--list-out", default="")
    ap.add_argument("--why", action="store_true")
    args = ap.parse_args(argv[1:])
    root = Path(git(Path.cwd(), "rev-parse", "--show-toplevel").strip())

    changed = changed_files(root, args.base)
    backend_mods: dict[str, str] = {}  # dotted -> changed path
    non_backend = []
    for f in changed:
        mod = module_of(f)
        if mod and not f.startswith("backend/tests/"):
            backend_mods[mod] = f  # test files self-select below, not graph seeds
        elif not f.startswith(("docs/", "frontend/", "backend/tests/")):
            non_backend.append(f)

    selected: dict[str, list[str]] = defaultdict(list)  # test file -> reasons
    smoke_triggered = False
    for f in changed:
        if f.startswith(API_POLICY_DIR) and f.endswith(".py"):
            smoke_triggered = True
        # CHANGED TEST FILES SELECT THEMSELVES (bake-off case 18984662: a
        # test-only commit selected 0 files — the dotted-ref graph cannot see
        # it because no test references a test; testmon ran 6 files). A gate
        # that doesn't run the tests the diff rewrote fails the tier's own
        # promise; this is identity selection, not closure.
        if (
            f.startswith("backend/tests/")
            and Path(f).name.startswith("test_")
            and f.endswith(".py")
            # identity selection needs a subject that EXISTS: git diff lists
            # deletions, and selecting a deleted file routes into
            # fast-backend-runner detector 1 (CANNOT-RUN: missing) — which
            # would block the very push that prunes a test, so the gate could
            # never ship its own corrections (--no-verify is forbidden).
            # A deleted test's REFERRERS still fail collection and the runner
            # names those ERRORs; only the phantom self-selection goes.
            and (root / f).exists()
        ):
            selected[f].append(f"changed test file: {f}")
        # CHANGED CONFTEST SELECTS ITS PYTEST TREE. conftest.py is neither a
        # production seed (lives under backend/tests/) nor a test file, so
        # without this rule a conftest edit selects NOTHING — exactly the
        # silent "tests stop running" trap the tier must not have. Directory
        # policy mirrors pytest's own scoping: a conftest applies to every
        # test collected beneath its directory.
        if f.startswith("backend/tests/") and Path(f).name == "conftest.py":
            for t in test_files(root):
                if t.startswith(f[: -len("conftest.py")]):
                    selected[t].append(f"conftest tree: {f}")

    # COMPOSE-CONFIG POLICY (bake-off a743cd64, the outcome arm's only closure
    # miss): test_ai_service_resource_limits.py has ZERO backend.* references —
    # it parses docker-compose.*.yml via Path and asserts on YAML content. No
    # Python import edge can exist; the test's dependency IS a filename. When
    # the diff changes a root-level compose file, tests whose text NAMES that
    # file ride. Scoped to docker-compose*.yml (the class the evidence shows)
    # rather than any data file — a basename-everything rule over-selects
    # (half the suite mentions pyproject.toml) with zero bake-off support.
    compose_changed = [
        f for f in changed if "/" not in f and f.startswith("docker-compose") and f.endswith(".yml")
    ]
    if compose_changed:
        for t in test_files(root):
            try:
                text = (root / t).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for f in compose_changed:
                if f in text:
                    selected[t].append(f"compose config changed: {f}")

    if backend_mods or smoke_triggered:
        index: dict[str, list[str]] = defaultdict(list)
        for t in test_files(root):
            for ref in dotted_refs(root, t):
                index[ref].append(t)
        # WP2.2 CLOSURE: direct referrers of the changed modules are only
        # depth 0 — the bake-off outcome arm charged BOTH selectors for
        # misses through untouched intermediaries (case 09872e45: route
        # change -> transitive test; the WP2.2 fixture turns this into a
        # deterministic repro). Walk producers first, then close depth>0
        # modules through referrers() with the same prefix semantics.
        # graph scan is the closure's only real cost (~4.7s full tree, A/B
        # measured): skip it entirely when no backend MODULE changed (test-
        # only diffs and the smoke-policy path need no graph at all).
        reach = closure(root, set(backend_mods)) if backend_mods else {}
        for dotted, src in sorted(backend_mods.items()):
            hits = sorted(referrers(index, dotted))
            if not hits:
                print(f"UNMAPPED: {src} (no test references {dotted})")
            for t in hits:
                selected[t].append(f"references {dotted} (changed: {src})")
        for dotted in sorted(reach):
            depth, seed = reach[dotted]
            if depth == 0:
                continue  # direct referrers already handled above
            hits = sorted(referrers(index, dotted))
            for t in hits:
                selected[t].append(f"transitive (depth {depth}): {dotted} imports {seed}")

    if smoke_triggered:
        for t in test_files(root):
            if t.startswith(SMOKE_GLOB):
                selected[t].append(f"directory policy: change under {API_POLICY_DIR}*")

    if non_backend:
        for f in sorted(non_backend):
            print(
                f"POLICY-SKIP: {f} (outside backend/**; fast tier covers backend + "
                "frontend; ai/*/tests and setup_lib/tests changes: run the full gate)"
            )

    ordered = sorted(selected)
    for t in ordered:
        print(f"SELECTED {t}")
        if args.why:
            for r in sorted(set(selected[t])):
                print(f"    because: {r}")
    if args.list_out:
        Path(args.list_out).write_text(
            "\n".join(ordered) + ("\n" if ordered else ""), encoding="utf-8"
        )
    print(f"SELECTED-BACKEND-FILES: {len(ordered)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
