import ast, os, re
ROOT = "/agents/agent-nemo2/workspace/backend/tests/chaos"
PAT = re.compile(r"#\s*(Implementation would|Should log)")
rows = []
for fn in sorted(os.listdir(ROOT)):
    if not fn.startswith("test_"): continue
    p = os.path.join(ROOT, fn)
    src = open(p, encoding="utf-8").read()
    tree = ast.parse(src)
    funcs = sorted([(n.lineno, n.name, n) for n in ast.walk(tree)
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test_")])
    lines = src.splitlines()
    for i, ln in enumerate(lines, 1):
        if PAT.search(ln):
            prec = [f for f in funcs if f[0] < i]
            owner = prec[-1] if prec else None
            marks = []
            if owner:
                for d in owner[2].decorator_list:
                    s = ast.unparse(d)
                    if "xfail" in s or "skip" in s or "timeout" in s: marks.append(s)
            rows.append((fn, i, owner[1] if owner else "??", owner[0] if owner else 0, marks, ln.strip()))
for r in rows:
    print("%s:%d owner=%s@%d marks=%s :: %s" % r)
print("TOTAL", len(rows))
