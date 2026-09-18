import ast, json, sys, difflib, textwrap, re

ORIG = '/agents/agent-nemo2/workspace/backend/services/alert_service.py'
MUT  = '/agents/agent-nemo2/workspace/mutants/backend/services/alert_service.py'
orig_src = open(ORIG).read()
orig_tree = ast.parse(orig_src)
orig_lines = orig_src.splitlines()

def methods(tree):
    out = {}
    for cn in ast.walk(tree):
        if isinstance(cn, ast.ClassDef):
            for m in cn.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out[(cn.name, m.name)] = m
        elif isinstance(tree, ast.Module):
            pass
    # top-level functions
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out[(None, n.name)] = n
    return out

OM = methods(orig_tree)

def body_src(lines, node, strip_doc=True):
    seg = lines[node.lineno-1: node.end_lineno]
    # drop signature: find first line ending with ':' at depth 0 of the header
    # simpler: use body start
    first = node.body[0]
    start = first.lineno - 1
    if strip_doc and isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
        start = first.end_lineno
    seg = lines[start: node.end_lineno]
    return textwrap.dedent(''.join(seg))

mut_src = open(MUT).read()
mut_tree = ast.parse(mut_src)
MM = {}
for cn in ast.walk(mut_tree):
    if isinstance(cn, ast.ClassDef):
        for m in cn.body:
            if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                MM[m.name] = m

def split_key(k):
    parts = k.split('ǁ')
    if len(parts) == 3:
        return parts[1], 'xǁ' + parts[1] + 'ǁ' + parts[2]
    return None, k.split('.')[-1]

def split_key3(k):
    parts = k.split('ǁ')
    if len(parts) == 3:
        import re as _re
        oname = _re.sub(r'__mutmut_\d+$', '', parts[2])
        return parts[1], 'xǁ'+parts[1]+'ǁ'+parts[2], oname
    raise SystemExit('unexpected key '+k)

surv = json.load(open(sys.argv[1]))
for k in surv:
    cls, mangled, oname = split_key3(k)
    node = MM.get(mangled)
    if node is None:
        print(f"### {k}\n  !! variant not found"); continue

    onode = OM.get((cls, oname)) or OM.get((None, oname))
    if onode is None:
        print(f"### {k}\n  !! original {oname} not found"); continue
    a = body_src(orig_lines, onode).rstrip('\n').splitlines()
    blines = mut_src.splitlines()
    b = body_src(blines, node).rstrip('\n').splitlines()
    d = [l for l in difflib.unified_diff(a, b, lineterm='', n=1) if not l.startswith(('---','+++','@@'))]
    print(f"### {k}")
    if not d:
        print("   (no body diff)")
    for l in d:
        print("  " + l)
