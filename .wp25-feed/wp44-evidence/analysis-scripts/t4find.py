"""Find narrow, REAL 2-hop chains: leaf <- inter <- top(route), top has a direct test.
Verify each edge comes from an actual import statement (not docstring prose)."""
import ast
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, "/tmp/wp25clone/scripts")
import fast_select as fs  # noqa: E402

root = Path("/tmp/wp25clone")
REF_RE = fs.REF_RE
tests = fs.test_files(root)
index = defaultdict(list)
for t in tests:
    for ref in fs.dotted_refs(root, t):
        index[ref].append(t)
inv = fs.producers_of(root)


def direct(d):
    return fs.referrers(index, d)


# module -> rel path
def rel_of(mod):
    return mod.replace(".", "/") + ".py"


def real_edge(src_mod, dst_mod):
    """Does src file actually IMPORT dst (relative-resolved AST edge or dotted)?"""
    rel = rel_of(src_mod)
    if src_mod.endswith("__init__"):
        rel = src_mod[: -len(".__init__")].replace(".", "/") + "/__init__.py"
    p = root / rel
    if not p.exists():
        return False
    text = p.read_text(encoding="utf-8", errors="replace")
    # dotted form present as text?
    if dst_mod in RECHECK(text):
        return True
    return False


def RECHECK(text):
    return text


def import_lines(src_mod, needle):
    rel = rel_of(src_mod)
    p = root / rel
    if not p.exists():
        return []
    out = []
    for i, line in enumerate((root / rel).read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if needle in line and ("import" in line):
            out.append(f"{rel}:{i}: {line.strip()[:90]}")
    return out


rows = []
for leaf in inv:
    if not leaf.startswith(("backend.services.", "backend.core.", "backend.models.", "backend.api.schemas.")):
        continue
    width = len(inv[leaf])  # narrowness of leaf
    for inter in inv[leaf]:
        if inter.startswith("backend.tests") or inter == leaf:
            continue
        # prefer non-package intermediates (no __init__) for a clean 3-file story
        for top in inv.get(inter, ()):
            if top.startswith("backend.tests") or top == leaf or top == inter:
                continue
            if leaf in inv.get(top, ()):  # would be depth-1 for top
                continue
            if not top.startswith("backend.api.routes.") or top.endswith("__init__"):
                continue
            d = direct(top)
            if not d:
                continue
            rows.append((width, leaf, inter, top, sorted(d)[0]))

rows.sort()
printed = 0
seen_leaf = set()
for width, leaf, inter, top, t in rows:
    if leaf in seen_leaf:
        continue
    # verify real import statements exist for both hops (skip __init__ intermediates)
    leaf_leaf = leaf.split(".")[-1]
    inter_tail = inter.split(".")[-1]
    l1 = import_lines(inter, leaf_leaf)
    l2 = import_lines(top, inter_tail)
    if not l1 or not l2:
        continue
    seen_leaf.add(leaf)
    print(f"[leaf producers={width}] leaf={leaf}\n   hop1: {l1[0]}\n   hop2: {l2[0]}\n   top={top}  direct-test={t}")
    printed += 1
    if printed >= 12:
        break
