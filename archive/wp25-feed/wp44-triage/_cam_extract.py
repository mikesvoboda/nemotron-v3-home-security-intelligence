import json, re, ast, difflib, sys

MUT = "/agents/agent-nemo2/workspace/mutants/backend/api/routes/cameras.py"
ORIG = "/agents/agent-nemo2/workspace/backend/api/routes/cameras.py"

surv = [l.strip() for l in open('/tmp/wp25/cameras-survivors.txt') if l.strip()]

orig_src = open(ORIG).read()
mut_src = open(MUT).read()
mtree = ast.parse(mut_src)
otree = ast.parse(orig_src)

def funcs(tree, src):
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            seg = ast.get_source_segment(src, node)
            if seg is not None:
                out.setdefault(node.name, seg)
    return out

mf = funcs(mtree, mut_src)
of = funcs(otree, orig_src)

result = {}
miss = []
for k in surv:
    # backend.api.routes.cameras.x__fn__mutmut_N
    tail = k.split('.')[-1]
    base = re.sub(r'__mutmut_\d+$', '', tail)   # x__fn
    idx = int(tail.split('__mutmut_')[-1])
    v = mf.get(tail)
    # baseline: prefer original function, strip leading x_
    short = base[2:] if base.startswith("x_") else base
    b = of.get(short) or of.get(base) or mf.get(short)
    if v is None or b is None:
        miss.append((k, v is None, b is None)); continue
    d = [l for l in difflib.unified_diff(b.splitlines(), v.splitlines(), lineterm="", n=1)
         if l and ((l.startswith(("-","+")) and not l.startswith(("---","+++"))) or l.startswith("@@"))]
    result[k] = d
json.dump({"res": result, "miss": miss}, open('/tmp/wp25/wp44-triage/_cam_diffs.json','w'), indent=1)
print("extracted:", len(result), "missed:", len(miss), file=sys.stderr)
for m in miss[:20]: print("MISS", m, file=sys.stderr)
