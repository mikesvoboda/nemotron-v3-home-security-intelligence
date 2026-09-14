import ast, os, re
ROOT = "/agents/agent-nemo2/workspace/backend/tests/chaos"
PAT = re.compile(r"#\s*(Implementation would|Should log)")
def owner_chain(tree, line):
    # all functions whose range contains line, outermost->innermost; return names
    best = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.lineno <= line <= (node.end_lineno or node.lineno):
            best.append((node.lineno, node.end_lineno, node.name))
    return best
for fn in sorted(os.listdir(ROOT)):
    if not fn.startswith("test_"): continue
    p = os.path.join(ROOT, fn)
    src = open(p, encoding="utf-8").read()
    tree = ast.parse(src)
    lines = src.splitlines()
    for i, ln in enumerate(lines, 1):
        if PAT.search(ln):
            ch = sorted(owner_chain(tree, i))
            print("%s:%d  chain=%s" % (fn, i, " < ".join(n for _,_,n in ch) or "MODULE-LEVEL"))
