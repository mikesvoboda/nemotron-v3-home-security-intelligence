#!/usr/bin/env python3
"""WP4.2: an unspecced-but-convertible mock-patch site is a licensed exception.

WP4.1's sweep raised autospec adoption to 95.5% (6,773/7,095 sites) and left
322 documented convertible-but-unspecced sites (unit 56 in-test reverts +
integration 229 fixture-surface policy + 37 in the unswept
benchmarks/chaos/e2e tiers). Nothing stopped a NEW one from landing: a plain
patch("a.b.c") accepts ANY signature, so the drift class Phase 4 exists to
kill could re-enter at any time. This gate closes the door, riding Phase 1's
ratchet (counts may only fall; every surviving site is a registry entry with
owner+kind, design 2026-09-15 §Phase 1) -- a NEW unspecced convertible site
fails CI as UNREGISTERED + RATCHET unspecced_patch, naming its id.

Measurement is THIS file (the classifier is loaded from autospec-sweep.py --
importlib, not a copy -- so gate and sweep can never disagree about what
`convertible` means; na forms -- new=/new_callable=/patch.dict/bare-name/
non-str target -- are the sweep's documented refusals and are not sites).
scripts/suppression-census.py imports sites_for_root() so the category has
one source of truth; scripts/ratchet-check.py enforces, unchanged.

ids are `relpath::scope::kN` (scope = enclosing class.Test.test / test,
omitted at module level; kN = ordinal within the scope, line order).
Deliberately NOT file:line: WP4.1's own gate collateral twice saw file:line
registry ids rot under batch edits (ssl_certs 880->927, preview_api
428->472 re-keys); with 322 seeded entries a line-keyed registry would churn
on every insertion. Drift cost paid instead: same-scope insertions renumber
later kN ids, which the ratchet surfaces as STALE+UNREGISTERED together
(loudly, as a rename -- never silently).

Modes:
    --count     [--root DIR]   the category count (default)
    --locations [--root DIR]   JSON [{id, reason}]  (the census emits this)
    --staged    [FILES...]     pre-commit fast path: fail (rc 1) if a site
                               sits on an ADDED line of the staged diff. The
                               tree legitimately carries 322 licensed sites,
                               so whole-file scanning at commit time would
                               block every commit touching those files; the
                               ratchet (CI, whole tree) is the completeness
                               layer.

Run: uv run python scripts/check-mock-spec.py            # --count default
Tests: uv run pytest scripts/test_check_mock_spec.py -q
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT_DEFAULT = Path(__file__).resolve().parent.parent
_SWEEP = Path(__file__).resolve().parent / "autospec-sweep.py"

_spec = importlib.util.spec_from_file_location("autospec_sweep_reuse", _SWEEP)
assert _spec and _spec.loader
_sweep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_sweep)
call_name = _sweep.call_name
classify = _sweep.classify

REASON_MAX = 100  # registry rows quote the rationale comment, bounded


def _scope_stack(tree: ast.AST) -> dict[int, list[str]]:
    """id(node) -> enclosing qualified scope path (class.Test.test)."""

    def visit(node: ast.AST, path: list[str], out: dict[int, list[str]]) -> None:
        for child in ast.iter_child_nodes(node):
            child_path = path
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                child_path = [*path, child.name]
            out[id(child)] = child_path
            visit(child, child_path, out)

    out: dict[int, list[str]] = {}
    visit(tree, [], out)
    return out


def _rationale(lines: list[str], lineno: int) -> str:
    """Nearest preceding standalone comment (up to 3 lines up) or a clean
    same-line trailing one -- WP4.1's revert doctrine put the class rationale
    directly above each reverted patch, so the registry can quote it."""
    text = lines[lineno - 1] if 0 < lineno <= len(lines) else ""
    if text.count("#") == 1 and not text.lstrip().startswith("#"):
        tail = text.split("#", 1)[1].strip()
        if tail:
            return tail[:REASON_MAX]
    for off in (1, 2, 3):
        i = lineno - 1 - off
        if i < 0:
            break
        stripped = lines[i].lstrip()
        if stripped.startswith("#"):
            return stripped.lstrip("# ").strip()[:REASON_MAX]
    return ""


def sites_with_lines(path: Path) -> list[dict]:
    """Convertible (unspecced, autospec-eligible) sites in line order, each
    with {id, reason, lineno}; the id's path segment is `path` as given."""
    try:
        src = path.read_text()
        tree = ast.parse(src)
    except SyntaxError, OSError:
        return []
    lines = src.splitlines()
    scopes = _scope_stack(tree)
    found = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and call_name(node) is not None
        and classify(node)[0] == "convertible"
    ]
    found.sort(key=lambda n: (n.lineno, n.col_offset))
    ordinals: dict[str, int] = {}
    out = []
    for node in found:
        scope = ".".join(scopes.get(id(node), []))
        ordinals[scope] = ordinals.get(scope, 0) + 1
        kn = f"k{ordinals[scope]}"
        out.append(
            {
                "id": f"{path}::{scope}::{kn}" if scope else f"{path}::{kn}",
                "reason": _rationale(lines, node.lineno),
                "lineno": node.lineno,
            }
        )
    return out


def sites_for_file(path: Path) -> list[dict]:
    return [{k: v for k, v in it.items() if k != "lineno"} for it in sites_with_lines(path)]


def sites_for_root(root: Path) -> list[dict]:
    """Every site under root/backend/tests, ids relative to root."""
    out = []
    for path in sorted((root / "backend/tests").rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        for it in sites_with_lines(path):
            it["id"] = rel + it["id"][len(str(path)) :]
            it.pop("lineno")
            out.append(it)
    return out


# ----------------------------------------------------------- staged path


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)


def _added_lines(root: Path, rel: str) -> set[int]:
    """Line numbers (new-file coords) the staged diff adds. A brand-new file
    (no HEAD blob) contributes its whole body -- line count upper-bounded by
    the staged blob's length at the call site."""
    exists = _git(root, "cat-file", "-e", f"HEAD:{rel}")
    if exists.returncode != 0:
        blob = _git(root, "show", f":{rel}")
        return set(range(1, len(blob.stdout.splitlines()) + 1))
    diff = _git(root, "diff", "--cached", "-U0", "--", rel)
    added: set[int] = set()
    new_ln = 0
    for line in diff.stdout.splitlines():
        if line.startswith("@@"):
            # @@ -old +new @@  -- U0 hunk headers: parse the +start
            try:
                new_ln = int(line.split("+")[1].split(" ", 1)[0].split(",")[0])
            except IndexError, ValueError:
                new_ln = 0
        elif line.startswith("+") and not line.startswith("+++"):
            added.add(new_ln)
            new_ln += 1
        elif line.startswith("-") or line.startswith("---"):
            pass  # removed lines don't exist in the new file
        elif line.startswith("\\"):
            pass  # "\ No newline at end of file"
        else:
            new_ln += 1
    return added


def check_staged(root: Path, files: list[str]) -> int:
    if not files:
        listed = _git(root, "diff", "--cached", "--name-only", "--diff-filter=ACM")
        files = [f for f in listed.stdout.splitlines() if f.endswith(".py")]
    offenders: list[str] = []
    for rel in files:
        if not rel.startswith("backend/tests"):
            continue  # the census's own denominator
        blob = _git(root, "show", f":{rel}")
        if blob.returncode != 0:
            continue  # staged-deleted or unreadable -- not our business here
        added = _added_lines(root, rel)
        if not added:
            continue
        tmp = root / ".git" / "check-mock-spec-staged"
        tmp.mkdir(exist_ok=True)
        probe = tmp / rel.replace("/", "__")
        probe.write_text(blob.stdout)
        try:
            for it in sites_with_lines(probe):
                if it["lineno"] in added:
                    offenders.append(f"{rel}{it['id'][len(str(probe)) :]}")
        finally:
            probe.unlink(missing_ok=True)
    for o in offenders:
        print(f"UNSPECCED MOCK: {o}", file=sys.stderr)
    if offenders:
        print(
            "\nAdd autospec=True (the sweep's convertible class), or license "
            "each site: a .github/suppression-registry.yml entry AND the "
            "hand-raised count in .github/suppression-baseline.json -- the "
            "ratchet reviews both in the same commit.",
            file=sys.stderr,
        )
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="WP4.2 unspecced-mock gate (ratchet category)")
    ap.add_argument("--root", default=str(REPO_ROOT_DEFAULT))
    ap.add_argument("--locations", action="store_true", help="JSON [{id, reason}]")
    ap.add_argument("--count", action="store_true", help="category count (default)")
    ap.add_argument("--staged", action="store_true", help="pre-commit fast path")
    ap.add_argument("files", nargs="*", help=argparse.SUPPRESS)
    args = ap.parse_args()
    root = Path(args.root).resolve()
    if args.staged:
        return check_staged(root, args.files)
    sites = sites_for_root(root)
    if args.locations:
        print(json.dumps(sites, indent=2))
        return 0
    print(len(sites))
    return 0


if __name__ == "__main__":
    sys.exit(main())
