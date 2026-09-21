#!/usr/bin/env python3
"""WP4.1 autospec sweep — raise mock-signature-detection adoption mechanically.

Why: 190 of 6,168 unit `patch(` sites (3.1% at the 2026-09-17 re-census; the
spec's 2.5% baseline counted a 7,493-site denominator that included trees
this census doesn't) carry `autospec=True`; integration carries zero
`autospec`/`spec_set` at all. An unqualified `patch("a.b.c")` accepts ANY
signature — renamed keyword, added required parameter, deleted parameter —
so a test can stay green against drifted production code forever. That is
precisely the drift class the 2026-09-12 revival recovered from, and the
Sep-15 autospec pass proved the failure mode is real (four `init_db` stubs
missing an attribute the real function reads on every path).

This tool rewrites the forms where `autospec=True` is mechanically correct
and REFUSES everything else — a conversion of a form the tool doesn't
understand would make a mock fail loudly and get the sweep reverted as
broken. Refusals are reported as `skipped-na` for human triage, never
guessed at:

  converts:  patch("dotted.path")            patch.object(obj, "attr")
             mocker.patch(...)               @patch(...) decorator
  refuses:   patch("bare-name")      -- no dots: nothing to resolve
             f-string / non-str target -- unresolvable statically
             patch(t, new=X) / two positionals -- `new` short-circuits spec
             patch(t, spec=/spec_set=)        -- already specced (weaker, but
                                                  the author chose it; upgrade
                                                  is a human call)
             patch.dict / patch.multiple      -- different call shape entirely

Usage:
    uv run python scripts/autospec-sweep.py [--census|--fix] PATH [PATH ...]

Default PATHs: backend/tests. Default mode: --census (read-only). --fix
rewrites in place, idempotently (a second pass converts nothing). Exit 0 in
both modes; the census line on stdout is the MEASURE artifact for commits:

    sites=6882 speced=190 skipped-na=212 files=713
"""

import argparse
import ast
import sys
from pathlib import Path

# call functions that mock-patch a target and therefore *can* carry autospec
PATCH_FUNCS = {"patch", "object", "dict", "multiple"}
# sub-forms where autospec simply doesn't apply — census puts them in
# skipped-na so nothing is silently dropped from the denominator
NA_SUBFORMS = {"dict", "multiple"}


def call_name(node: ast.Call) -> str | None:
    """Return the mock-patch family name for a call node, else None."""
    f = node.func
    if isinstance(f, ast.Name) and f.id in ("patch", "mock", "mocker"):
        return "patch"
    if isinstance(f, ast.Attribute) and f.attr in PATCH_FUNCS:
        v = f.value
        # patch.X, mock.patch.X, mocker.patch.X (attribute chains) — accept
        # any chain whose attr names a mock-patch form; plain `foo.patch` in
        # test code IS the import-alias shape (from unittest import mock).
        if (isinstance(v, ast.Name) and v.id in ("mock", "mocker", "patch")) or isinstance(
            v, ast.Attribute
        ):
            return f.attr
        if isinstance(v, ast.Attribute) and v.attr == "patch":
            return f.attr
    return None


def classify(node: ast.Call) -> tuple[str, str]:
    """(kind, reason): kind in {speced, convertible, na}; reason free text."""
    kw = {k.arg for k in node.keywords}
    if {"autospec", "spec", "spec_set"} & kw:
        return ("speced", "")
    name = call_name(node)
    if name in NA_SUBFORMS:
        return ("na", f"patch.{name}")
    if "new" in kw:
        return ("na", "new= given")
    pos = node.args
    if name == "object":
        if len(pos) == 2 and isinstance(pos[1], ast.Constant) and isinstance(pos[1].value, str):
            return ("convertible", "")
        if len(pos) >= 3:
            return ("na", "new positional")
        return ("na", "non-str attribute")
    # plain patch(...)
    if len(pos) >= 2:
        return ("na", "new positional")
    if len(pos) == 1:
        a = pos[0]
        if isinstance(a, ast.Constant) and isinstance(a.value, str):
            if "." in a.value:
                return ("convertible", "")
            return ("na", "bare-name target")
        return ("na", "non-string target")
    return ("na", "no target")


def scan_file(path: Path) -> tuple[list, list, int]:
    """(convertible nodes, all-family nodes, parse-error flag)."""
    try:
        tree = ast.parse(path.read_text(), str(path))
    except SyntaxError:
        return [], [], 1
    conv, fam = [], []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and call_name(node) is not None:
            fam.append(node)
            if classify(node)[0] == "convertible":
                conv.append(node)
    return conv, fam, 0


def insert_autospec(src: str, nodes: list) -> str:
    """Insert `autospec=True` before each call's closing paren.

    ast offsets are UTF-8 BYTE offsets (end_col_offset points just after the
    ')'), so splicing happens on bytes and decodes once at the end —
    char-offset arithmetic would silently corrupt any file with non-ASCII
    earlier on the same line. Applied right-to-left so earlier insertions
    don't shift later offsets.

    Shapes: `f(a)` -> `f(a, autospec=True)`; `f(a,)` -> `f(a, autospec=True)`;
    multi-line black-style call ending with a trailing comma gets its own
    line at the last argument's indent (keeps the file prettier-clean).
    """
    b = src.encode("utf-8")
    line_starts = [0]
    for i, ch in enumerate(b):
        if ch == 0x0A:
            line_starts.append(i + 1)

    def insert_at(rpar: int) -> bytes:
        # scan back over spaces/tabs before ')'
        q = rpar
        while q > 0 and b[q - 1] in (0x20, 0x09):
            q -= 1
        if q > 0 and b[q - 1] == 0x0A:
            # ')' sits on its own line: multi-line call. Insert our own line
            # at the last content line's indent.
            p = q - 1  # index of the '\n' that ends the last content line
            while p > 0:
                ls = max(s for s in line_starts if s < p)
                seg = b[ls:p]  # that line's content, newline excluded
                if seg.strip():
                    indent = seg[: len(seg) - len(seg.lstrip(b" \t"))]
                    if seg.rstrip().endswith(b","):
                        return b[:q] + indent + b"autospec=True,\n" + b[q:]
                    # last arg without trailing comma: add one, then our line
                    return b[:p] + b",\n" + indent + b"autospec=True\n" + b[p + 1 :]
                p = ls  # blank line: step up
            return b[:q] + b"autospec=True,\n" + b[q:]
        before = b[:rpar].rstrip()
        sep = b"" if before.endswith((b"(", b",")) else b","
        tail = b"," if before.endswith(b",") else b""
        return b[:rpar] + sep + b" autospec=True" + tail + b[rpar:]

    rparts = sorted(
        (line_starts[n.end_lineno - 1] + n.end_col_offset - 1 for n in nodes),
        reverse=True,
    )
    for rpar in rparts:
        b = insert_at(rpar)
    return b.decode("utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--census", action="store_true", help="report counts (default)")
    g.add_argument("--fix", action="store_true", help="rewrite files in place")
    ap.add_argument("paths", nargs="*", default=["backend/tests"])
    args = ap.parse_args()

    sites = speced = na = nfiles = errors = 0
    converted_files = 0
    converted_sites = 0
    for root in args.paths:
        rp = Path(root)
        files = [rp] if rp.is_file() else sorted(rp.rglob("*.py"))
        for f in (x for x in files if "__pycache__" not in x.parts):
            conv, fam, err = scan_file(f)
            if err:
                errors += 1
                print(f"parse-error: {f}", file=sys.stderr)
                continue
            if not fam:
                continue
            nfiles += 1
            for node in fam:
                kind, _ = classify(node)
                if kind == "speced":
                    speced += 1
                    sites += 1
                elif kind == "convertible":
                    sites += 1
                else:
                    na += 1
            # NOTE: `na` sites are deliberately NOT in `sites` — the pinned
            # test proves it (2 convertible+speced sites and 1 patch.dict
            # report sites=2, not 3): autospec is inapplicable to them, so
            # counting them would dilute the adoption percentage the sweep
            # is measured on.
            if args.fix and conv:
                src = f.read_text()
                f.write_text(insert_autospec(src, conv))
                converted_files += 1
                converted_sites += len(conv)

    if args.fix:
        print(f"{converted_sites} converted, {na} skipped ({converted_files} files)")
    else:
        print(
            f"sites={sites} speced={speced} skipped-na={na} files={nfiles}"
            + (f" parse-errors={errors}" if errors else "")
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
