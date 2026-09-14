#!/usr/bin/env python3
"""T2 dead-fixture consumer census (READ-ONLY; no pytest, no imports of repo code).

For every fixture name defined in any conftest under backend/tests/, counts
GENUINE consumers: functions (tests or other fixtures) that list the name as a
parameter, plus request.getfixturevalue("name") sites. Ignores bare textual
mentions (docstrings/comments/imports/attributes) — the ledger's false-positive
class. Prints JSON.
"""
import ast, json, os, sys, collections

ROOT = "/agents/agent-nemo2/workspace/backend/tests"

def is_fixture_deco(node):
    for d in node.decorator_list:
        t = d.func if isinstance(d, ast.Call) else d
        if isinstance(t, ast.Attribute) and t.attr == "fixture":
            return True
        if isinstance(t, ast.Name) and t.id == "fixture":
            return True
    return False

def getfixturevalue_names(tree):
    out = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "getfixturevalue" and node.args
                and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
            out.append((node.args[0].value, node.lineno))
    return out

fixtures = collections.defaultdict(list)   # name -> [(conftest_path, deco_line, def_line, end_line, scope)]
consumers = collections.defaultdict(list)  # name -> [(file, func, line, kind)]
all_trees = {}

for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d != "__pycache__"]
    for fn in filenames:
        if not fn.endswith(".py"):
            continue
        path = os.path.join(dirpath, fn)
        try:
            tree = ast.parse(open(path, encoding="utf-8").read(), filename=path)
        except SyntaxError as e:
            print("PARSE-ERROR %s: %s" % (path, e), file=sys.stderr)
            continue
        all_trees[path] = tree
        rel = os.path.relpath(path, ROOT)
        # fixture definitions (conftest or any file — fixtures also live in test modules)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and is_fixture_deco(node):
                scope = "function"
                for d in node.decorator_list:
                    if isinstance(d, ast.Call):
                        for kw in d.keywords:
                            if kw.arg == "scope" and isinstance(kw.value, ast.Constant):
                                scope = kw.value.value
                fixtures[node.name].append({"file": rel, "deco": node.decorator_list[0].lineno,
                                            "def": node.lineno, "end": node.end_lineno, "scope": scope})
        # consumers: params + getfixturevalue
        for name, line in getfixturevalue_names(tree):
            consumers[name].append({"file": rel, "func": "<getfixturevalue>", "line": line, "kind": "getfixturevalue"})
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                params = [a.arg for a in node.args.args] + [a.arg for a in node.args.kwonlyargs]
                kind = "test" if node.name.startswith("test_") else ("fixture" if is_fixture_deco(node) else "helper")
                for p in params:
                    consumers[p].append({"file": rel, "func": node.name, "line": node.lineno, "kind": kind})

TARGETS = ["template_database", "worker_database", "authenticated_client", "mock_threat_detector",
           "mock_model_zoo", "enrichment_scenarios", "patch_database_dependency",
           "patch_redis_dependency", "session", "mock_redis", "fault_injector",
           "cleanup_stale_databases"]
out = {}
for t in TARGETS:
    defs = fixtures.get(t, [])
    cons = [c for c in consumers.get(t, [])]
    # split consumers into: inside the defining conftest (self-referential), other conftests, test files, non-test helpers
    def_files = {d["file"] for d in defs}
    cons_test = [c for c in cons if c["file"].startswith("test_") or os.path.basename(c["file"]).startswith("test_")]
    cons_test = [c for c in cons if os.path.basename(c["file"]).startswith("test_")]
    cons_conf = [c for c in cons if os.path.basename(c["file"]) == "conftest.py"]
    cons_other = [c for c in cons if c not in cons_test and c not in cons_conf]
    out[t] = {"definitions": defs, "consumers_total": len(cons),
              "consumers_test_files": cons_test, "consumers_conftest": cons_conf,
              "consumers_other": cons_other}
print(json.dumps(out, indent=1))
