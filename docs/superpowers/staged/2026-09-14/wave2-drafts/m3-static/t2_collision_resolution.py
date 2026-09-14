#!/usr/bin/env python3
"""Which conftest's `session` / `mock_redis` do consumers actually resolve to?
pytest resolves a fixture name by directory proximity: nearest conftest (or the
test module itself) wins. So a consumer under integration/ hits integration's
twin; a consumer under unit/ etc. hits root's twin (unless the module defines
its own local fixture of the same name, which shadows both).
READ-ONLY AST. No imports of repo code, no pytest.
"""
import ast, os, collections, json

ROOT = "/agents/agent-nemo2/workspace/backend/tests"
TARGETS = ("session", "mock_redis")

def is_fixture_dec(node):
    for d in node.decorator_list:
        t = d.func if isinstance(d, ast.Call) else d
        if (isinstance(t, ast.Attribute) and t.attr == "fixture") or (isinstance(t, ast.Name) and t.id == "fixture"):
            return True
    return False

def local_fixture_names(tree):
    s = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and is_fixture_dec(node):
            s.add(node.name)
    return s

def requested_names(tree):
    """params of test functions + all functions (fixtures may request too) + getfixturevalue"""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            params = [a.arg for a in node.args.args]
            for p in params:
                out.append((node.name, node.lineno, p))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "getfixturevalue" \
           and node.args and isinstance(node.args[0], ast.Constant):
            out.append(("<getfixturevalue>", node.lineno, node.args[0].value))
    return out

# conftest chain per directory
conftests = {}
for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d != "__pycache__"]
    if "conftest.py" in filenames:
        p = os.path.join(dirpath, "conftest.py")
        tree = ast.parse(open(p, encoding="utf-8").read(), filename=p)
        conftests[os.path.relpath(dirpath, ROOT)] = local_fixture_names(tree)

def resolve(relfile, name):
    """return 'module', 'conftest:<dir>', or None — nearest definition for this file."""
    modpath = os.path.dirname(relfile)
    tree_local = None
    d = modpath
    parts = []
    # nearest conftest walking up from the file's dir to ROOT
    cur = d
    while True:
        if cur in conftests and name in conftests[cur] and cur != ".":
            return "conftest:%s" % cur
        if cur in conftests and name in conftests[cur] and cur == ".":
            return "conftest:ROOT"
        if cur == ".":
            break
        cur = os.path.dirname(cur) if cur not in ("", ".") else "."
    return None

report = collections.defaultdict(list)
for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d != "__pycache__"]
    for fn in sorted(filenames):
        if not fn.endswith(".py"):
            continue
        path = os.path.join(dirpath, fn)
        rel = os.path.relpath(path, ROOT)
        try:
            tree = ast.parse(open(path, encoding="utf-8").read(), filename=path)
        except SyntaxError:
            continue
        locals_ = local_fixture_names(tree)
        for tname in TARGETS:
            hits = [(f, ln, p) for (f, ln, p) in requested_names(tree) if p == tname]
            if not hits:
                continue
            if tname in locals_ and rel != "conftest.py":
                tgt = "module-local (%s)" % rel
            else:
                tgt = resolve(rel, tname) or "UNRESOLVED"
            report[tname].append({"file": rel, "resolves_to": tgt, "sites": hits[:400], "count": len(hits)})

for t in TARGETS:
    print("### %s" % t)
    agg = collections.Counter()
    for e in report[t]:
        agg[e["resolves_to"]] += e["count"]
    for k, v in agg.most_common():
        print("   -> %-50s %d param-sites" % (k, v))
    # per-file detail for root resolution
    print("   files resolving to root conftest:")
    for e in report[t]:
        if e["resolves_to"] == "conftest:ROOT":
            print("      %s  (%d sites, first lines %s)" % (e["file"], e["count"], [s[1] for s in e["sites"][:3]]))
    print("   files resolving to integration conftest:")
    for e in report[t]:
        if e["resolves_to"] == "conftest:integration":
            print("      %s  (%d sites)" % (e["file"], e["count"]))
    print()
