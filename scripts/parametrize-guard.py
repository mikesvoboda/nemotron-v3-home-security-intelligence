#!/usr/bin/env python3
"""parametrize-guard — M3 Task 8 (audit Part 4): merge-safe parametrize clusters.

Reports which same-class test methods are TRUE parametrize duplicates and which
look like duplicates but are NOT merge-safe, so a consolidation can never fold
distinct assertions into one parametrize list.

Merge rule (audit Part 7 #1: intra-(file,class) only):
  Two test methods in the same class are MERGE-SAFE candidates iff their ASTs
  are structurally identical modulo literal values (Constant nodes masked) AND
  their pytest.raises(match=...) buckets are equal. Methods whose raises-match
  values differ are GUARDED: each distinct match value must keep its own test
  (or its own parametrized `match` parameter, which is a *different* refactor
  that this tool deliberately does not propose).

The "41 false-identical" lesson (ledger T8-prep / t7-lists.md §6): method COUNT
alone overstates mergeability — TestValidateDedupKey has 39 methods but only the
28-'invalid characters' bucket merges; the other 11 carry 4 distinct matches,
6 no-raises bodies, and 2 empty/whitespace variants that are genuinely distinct
inputs, not dupes.

Usage:
    uv run python scripts/parametrize-guard.py [PATH ...]     # default backend/tests
    uv run python scripts/parametrize-guard.py --min N        # report classes with >= N methods (default 8)
    uv run python scripts/parametrize-guard.py --json         # machine-readable report
    uv run python scripts/parametrize-guard.py --self-test    # stdlib micro-cases, no repo needed

Exit: 0 report emitted OK; 1 parse failure on a scanned file (loud, never silent).
This tool REPORTS; it never edits. Merges are hand-applied per cluster with the
before/after member counts recorded in the ledger (the report IS the T8 row).
"""

from __future__ import annotations

import argparse
import ast
import collections
import json
import sys
import tempfile
import textwrap
from pathlib import Path

DEFAULT_MIN = 8


def _masked(node: ast.AST) -> str:
    """AST dump of a method with (a) every literal replaced by a sentinel and
    (b) the method NAME canonicalized, so bodies that differ ONLY in input
    constants (and their test_* names) hash equal. Everything else — the call
    graph, attr paths, decorators, arg shape, and `def` vs `async def` — stays
    in the key, so a body calling a different function is NOT a dupe.

    NOTE on match=: the raises match literal is masked here too, so body
    identity alone would let `'cannot be empty'` bucket with `'invalid
    characters'`. The caller's bucket key pairs this with raises_matches() —
    real match strings — which is the guard that keeps the 28-member
    'invalid characters' cluster from swallowing the other 11 methods.
    """
    import copy

    n2 = copy.deepcopy(node)
    if isinstance(n2, ast.FunctionDef | ast.AsyncFunctionDef):
        n2.name = "_canonical_"
    for sub in ast.walk(n2):
        if isinstance(sub, ast.Constant):
            sub.value = "__LIT__"
            for attr in ("kind",):
                if hasattr(sub, attr):
                    setattr(sub, attr, None)
    return ast.dump(n2)


def raises_matches(fn: ast.FunctionDef) -> tuple[str, ...]:
    """Sorted distinct pytest.raises match= literals in this method (any
    position). Empty tuple = no-raises body."""
    out = []
    for n in ast.walk(fn):
        if isinstance(n, ast.Call):
            try:
                fname = ast.unparse(n.func)
            except Exception:  # pragma: no cover - exotic py versions
                fname = ""
            if fname in ("pytest.raises", "raises"):
                for kw in n.keywords:
                    if kw.arg == "match":
                        out.append(ast.unparse(kw.value))
                for extra in n.args[2:]:  # match is 2nd positional after exc type
                    out.append("pos:" + ast.unparse(extra))
    return tuple(sorted(set(out)))


def analyze_class(cls: ast.ClassDef) -> dict:
    """Bucket the class's test methods by (masked-body, raises-bucket).

    A bucket with >=2 members is a merge-safe parametrize cluster; singleton
    buckets that merely share the raises bucket with another body are the
    guarded near-misses and are reported separately for the ledger's honesty
    (they LOOK mergeable by raises-bucket but are not body-identical)."""
    meths = [
        m
        for m in cls.body
        if isinstance(m, ast.FunctionDef | ast.AsyncFunctionDef) and m.name.startswith("test_")
    ]
    decorated = [
        m
        for m in meths
        if any(
            (
                isinstance(d, ast.Call)
                and getattr(d.func, "id", getattr(d.func, "attr", "")) == "parametrize"
            )
            for d in m.decorator_list
        )
    ]
    buckets: dict[tuple[str, tuple[str, ...]], list[ast.FunctionDef]] = collections.defaultdict(
        list
    )
    for m in meths:
        buckets[(_masked(m), raises_matches(m))].append(m)
    mergeable = {k: v for k, v in buckets.items() if len(v) >= 2}
    merge_members = sum(len(v) for v in mergeable.values())
    # distinct raises-match values across the class: each must survive any merge
    match_values = collections.Counter()
    for m in meths:
        for mv in raises_matches(m):
            match_values[mv] += 1
    return {
        "class": cls.name,
        "lines": [cls.lineno, cls.end_lineno or cls.lineno],
        "methods": len(meths),
        "already_parametrized": len(decorated),
        "merge_safe_members": merge_members,
        "merge_safe_clusters": [
            {
                "size": len(v),
                "members": [m.name for m in v],
                "raises_match": list(k[1]),
            }
            for k, v in sorted(mergeable.items(), key=lambda kv: -len(kv[1]))
        ],
        "guarded_match_values": dict(match_values),
        "distinct_bodies": len(buckets),
    }


def scan_file(path: Path, min_methods: int) -> list[dict]:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(path))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            rep = analyze_class(node)
            if rep["methods"] >= min_methods:
                rep["file"] = str(path)
                out.append(rep)
    return out


def scan(paths: list[Path], min_methods: int) -> list[dict]:
    results = []
    for p in paths:
        files = [p] if p.is_file() else sorted(p.rglob("test_*.py"))
        for f in files:
            if "__pycache__" in f.parts or "node_modules" in f.parts:
                continue
            try:
                results.extend(scan_file(f, min_methods))
            except SyntaxError as e:  # loud per hard rule: no silent skips
                print(f"[ERROR] parse failure {f}: {e}", file=sys.stderr)
                raise SystemExit(1) from None
    results.sort(key=lambda r: -r["merge_safe_members"])
    return results


# ------------------------- self-test (stdlib, no repo) -------------------------

_SELF_FIXTURE = textwrap.dedent("""
    import pytest

    class TestDedupLike:
        def test_a(self):
            with pytest.raises(ValueError, match="invalid characters"):
                fn("a!b")
        def test_b(self):
            with pytest.raises(ValueError, match="invalid characters"):
                fn("c@d")
        def test_c(self):
            with pytest.raises(ValueError, match="cannot be empty"):
                fn("")
        def test_d(self):
            assert other(fn("x"))

    class TestGuardedNotDupe:
        def test_a(self):
            assert fn("x") == 1
        def test_b(self):
            assert fn("y") == 2
        def test_c(self):
            assert fn("z") == 3
""").strip()


def self_test() -> int:
    import contextlib
    import io

    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "test_fixture.py"
        f.write_text(_SELF_FIXTURE, encoding="utf-8")
        # min_methods=1 so both classes report
        reps = {r["class"]: r for r in scan([f], min_methods=1)}

    checks = []

    def check(name, cond):
        checks.append((name, cond))

    d = reps["TestDedupLike"]
    check("dedup: 4 methods", d["methods"] == 4)
    # test_a/test_b differ only in the literal -> ONE merge-safe cluster of 2
    check("dedup: one 2-member cluster", [c["size"] for c in d["merge_safe_clusters"]] == [2])
    check(
        "dedup: cluster members are a,b",
        sorted(d["merge_safe_clusters"][0]["members"]) == ["test_a", "test_b"],
    )
    # ast.unparse normalizes string literals to single quotes
    check(
        "dedup: cluster carries its shared match",
        d["merge_safe_clusters"][0]["raises_match"] == ["'invalid characters'"],
    )
    # distinct matches each survive (guard accounting)
    gm = d["guarded_match_values"]
    check("dedup: 2x invalid-characters", gm.get("'invalid characters'") == 2)
    check("dedup: 1x cannot-be-empty", gm.get("'cannot be empty'") == 1)
    check("dedup: no-raises body counted separately", d["distinct_bodies"] == 3)

    g = reps["TestGuardedNotDupe"]
    # same body shape, 3 members, no raises -> merges fine (xclip-style class)
    check("guard: 3-method single cluster", [c["size"] for c in g["merge_safe_clusters"]] == [3])
    check("guard: no match guards", g["guarded_match_values"] == {})

    # negative: differing attr path must NOT bucket together
    neg = _SELF_FIXTURE.replace('assert fn("x") == 1', 'assert fn2("x") == 1')
    with tempfile.TemporaryDirectory() as td:
        f2 = Path(td) / "test_neg.py"
        f2.write_text(neg, encoding="utf-8")
        reps2 = {r["class"]: r for r in scan([f2], min_methods=1)}
    # test_a now calls fn2() -> its own bucket; b/c still merge => 2 buckets
    check(
        "negative: different callee splits buckets",
        reps2["TestGuardedNotDupe"]["distinct_bodies"] == 2,
    )
    check(
        "negative: remaining cluster is b,c only",
        [c["size"] for c in reps2["TestGuardedNotDupe"]["merge_safe_clusters"]] == [2],
    )

    fails = [n for n, ok in checks if not ok]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        for n, ok in checks:
            print(f"  {'PASS' if ok else 'FAIL'}  {n}")
    print(buf.getvalue(), end="")
    print(f"parametrize-guard self-test: {len(checks) - len(fails)}/{len(checks)} pass")
    return 1 if fails else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="*", default=None)
    ap.add_argument("--min", type=int, default=DEFAULT_MIN, metavar="N")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()
    root = Path("backend/tests")
    paths = [Path(p) for p in (args.paths or [root])]
    if not paths[0].exists():
        print(f"[ERROR] path not found: {paths[0]}", file=sys.stderr)
        return 1
    reps = scan(paths, args.min)
    if args.json:
        print(json.dumps(reps, indent=2))
        return 0
    total_members = sum(r["merge_safe_members"] for r in reps)
    for r in reps:
        print(
            f"== {r['file']}::{r['class']}  methods={r['methods']} "
            f"merge-safe={r['merge_safe_members']} distinct-bodies={r['distinct_bodies']} "
            f"guards={r['guarded_match_values'] or '-'}"
        )
        for c in r["merge_safe_clusters"]:
            print(
                f"   x{c['size']} match={c['raises_match'] or '-'}: {', '.join(c['members'][:6])}"
                + ("…" if c["size"] > 6 else "")
            )
    print(f"TOTAL merge-safe members across {len(reps)} classes: {total_members}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
