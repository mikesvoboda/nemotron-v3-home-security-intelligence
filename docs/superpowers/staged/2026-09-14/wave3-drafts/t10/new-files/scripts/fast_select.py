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
backend/tests/contracts/ (4 test files at draft time: test_api_contracts,
test_openapi_schema_validation, test_schemathesis_contracts,
test_websocket_contracts - the CI-named contracts tier).

Usage: fast_select.py --base REF [--list-out FILE] [--why]
Stdout: human report ending in machine lines:
  SELECTED-BACKEND-FILES: N
Exit: 0 report produced (selection may be empty), 2 git failure.

Inert-additive (M1 constraint): scripts/ is outside pytest testpaths; the
paired scripts/test_fast_select.py is not collected by validate.sh until the
--fast tier lands. The regex also catches prose/docstrings mentioning dotted
paths - over-selection direction only, harmless under an advisory tier.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REF_RE = re.compile(r"backend(?:\.[A-Za-z_][A-Za-z0-9_]*)+")
API_POLICY_DIR = "backend/api/"
SMOKE_GLOB = "backend/tests/contracts"


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True
    )
    if proc.returncode != 0:
        print(f"git {' '.join(args)} failed: {proc.stderr.strip()}", file=sys.stderr)
        raise SystemExit(2)
    return proc.stdout


def changed_files(root: Path, base: str) -> list[str]:
    # Tracked diff (renames/deletions surface through git's own filter) plus
    # untracked-not-ignored files, so an unsaved new test still selects.
    files = set(git(root, "diff", "--name-only", base).splitlines())
    files |= set(
        git(root, "ls-files", "--others", "--exclude-standard").splitlines()
    )
    return sorted(files)


def module_of(rel: str) -> str | None:
    """backend/services/alert_service.py -> backend.services.alert_service."""
    if not rel.endswith(".py") or not rel.startswith("backend/"):
        return None
    return rel[: -len(".py")].replace("/", ".")


def test_files(root: Path) -> list[str]:
    out = git(root, "ls-files", "-z", "backend/tests").split("\0")
    return [f for f in out if Path(f).name.startswith("test_") and f.endswith(".py")]


def dotted_refs(root: Path, rel_test: str) -> set[str]:
    try:
        text = (root / rel_test).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    return set(REF_RE.findall(text))


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
        if mod:
            backend_mods[mod] = f
        elif not f.startswith(("docs/", "frontend/")):
            non_backend.append(f)

    selected: dict[str, list[str]] = defaultdict(list)  # test file -> reasons
    smoke_triggered = False
    for f in changed:
        if f.startswith(API_POLICY_DIR) and f.endswith(".py"):
            smoke_triggered = True

    if backend_mods or smoke_triggered:
        index: dict[str, list[str]] = defaultdict(list)
        for t in test_files(root):
            for ref in dotted_refs(root, t):
                index[ref].append(t)
        for dotted, src in sorted(backend_mods.items()):
            hits = sorted(referrers(index, dotted))
            if not hits:
                print(f"UNMAPPED: {src} (no test references {dotted})")
            for t in hits:
                selected[t].append(f"references {dotted} (changed: {src})")

    if smoke_triggered:
        for t in test_files(root):
            if t.startswith(SMOKE_GLOB):
                selected[t].append(f"directory policy: change under {API_POLICY_DIR}*")

    if non_backend:
        for f in sorted(non_backend):
            print(f"POLICY-SKIP: {f} (outside backend/**; fast tier covers backend + "
                  "frontend; ai/*/tests and setup_lib/tests changes: run the full gate)")

    ordered = sorted(selected)
    for t in ordered:
        print(f"SELECTED {t}")
        if args.why:
            for r in sorted(set(selected[t])):
                print(f"    because: {r}")
    if args.list_out:
        Path(args.list_out).write_text("\n".join(ordered) + ("\n" if ordered else ""), encoding="utf-8")
    print(f"SELECTED-BACKEND-FILES: {len(ordered)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
