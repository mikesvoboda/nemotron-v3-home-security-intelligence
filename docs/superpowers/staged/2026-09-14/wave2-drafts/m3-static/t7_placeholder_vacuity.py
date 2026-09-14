#!/usr/bin/env python3
"""For each chaos placeholder-marker line: enclosing test, and whether that test
has any real assertion (assert / pytest.raises / pytest.warns / fail). READ-ONLY AST + line scan.
Also lists ALL chaos test functions with zero assertions (audit 3.1 census re-check).
"""
import ast, os, re, json

ROOT = "/agents/agent-nemo2/workspace/backend/tests/chaos"
PAT = re.compile(r"#\s*(Implementation would|Should log)")

class AssertCounter(ast.NodeVisitor):
    def __init__(self):
        self.asserts = 0; self.raises = 0; self.warns = 0; self.fails = 0
    def visit_Assert(self, node):
        self.asserts += 1
    def visit_Call(self, node):
        f = node.func
        s = ast.unparse(f) if hasattr(ast, "unparse") else ""
        if s in ("pytest.raises",): self.raises += 1
        elif s in ("pytest.warns",): self.warns += 1
        elif s in ("pytest.fail", "self.fail", "fail"): self.fails += 1
        self.generic_visit(node)

def analyze(path):
    src = open(path, encoding="utf-8").read()
    lines = src.splitlines()
    tree = ast.parse(src, filename=path)
    funcs = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            # skip nested? use only functions whose body range contains no duplicate; fine
            ac = AssertCounter(); ac.visit(node)
            funcs.append(node)
    # placeholder sites
    site_rows = []
    for i, ln in enumerate(lines, 1):
        if PAT.search(ln):
            owner = None
            for f in funcs:
                if f.lineno <= i <= (f.end_lineno or f.lineno):
                    if owner is None or f.lineno > owner.lineno:
                        owner = f
            ac = AssertCounter()
            if owner is not None: ac.visit(owner)
            site_rows.append({"line": i, "text": ln.strip(),
                              "test": owner.name if owner else None,
                              "test_line": owner.lineno if owner else None,
                              "asserts": ac.asserts, "raises": ac.raises, "warns": ac.warns,
                              "marks_xfail": bool(owner) and any(
                                  "xfail" in ast.unparse(d) for d in owner.decorator_list),
                              "marks_skip": bool(owner) and any(
                                  "skip" in ast.unparse(d) for d in owner.decorator_list)})
    zero = []
    for f in funcs:
        ac = AssertCounter(); ac.visit(f)
        if ac.asserts == 0 and ac.raises == 0 and ac.warns == 0:
            zero.append({"test": f.name, "line": f.lineno, "mock_only": False})
    return site_rows, zero, len(funcs)

total_sites = 0; total_zero = 0; total_funcs = 0
for fn in sorted(os.listdir(ROOT)):
    if not fn.startswith("test_") or not fn.endswith(".py"): continue
    rows, zero, nf = analyze(os.path.join(ROOT, fn))
    total_sites += len(rows); total_zero += len(zero); total_funcs += nf
    if rows or zero:
        print("== %s (%d test funcs, %d placeholder sites, %d zero-assert)" % (fn, nf, len(rows), len(zero)))
        for r in rows:
            print("   :%-4s test=%s@%s assert=%d raises=%d xfail=%s skip=%s | %s" %
                  (r["line"], r["test"], r["test_line"], r["asserts"], r["raises"], r["marks_xfail"], r["marks_skip"], r["text"][:70]))
        if zero:
            print("   zero-assert tests:", ", ".join("%s@%d" % (z["test"], z["line"]) for z in zero))
print("TOTALS: placeholder sites=%d ; chaos test funcs=%d ; zero-assert=%d" % (total_sites, total_funcs, total_zero))
