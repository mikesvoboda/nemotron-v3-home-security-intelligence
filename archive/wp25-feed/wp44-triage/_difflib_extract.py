import json, re, ast, difflib, sys

MUT = "/agents/agent-nemo2/workspace/mutants/backend/services/batch_aggregator.py"
ORIG = "/agents/agent-nemo2/workspace/backend/services/batch_aggregator.py"
SURV = json.load(open("/tmp/wp25/wp44-triage/_surv_batch_agg.json"))

orig_src = open(ORIG).read()
mut_src = open(MUT).read()

def funcs(tree, src):
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            seg = ast.get_source_segment(src, node)
            if seg is not None:
                out.setdefault(node.name, seg)
    return out

print("parsing mutant copy...", file=sys.stderr)
mtree = ast.parse(mut_src)
otree = ast.parse(orig_src)
mf = funcs(mtree, mut_src)
of = funcs(otree, orig_src)

# baselines
def pick_variant(fn, i):
    # fn like "get_memory_pressure_level" or "ǁBatchAggregatorǁ_close_batch_for_size_limit"
    # variant names observed: x_get_memory_pressure_level__mutmut_1, xǁBatchAggregatorǁ_close_batch_for_size_limit__mutmut_5
    name = f"{fn}__mutmut_{i}"
    return mf.get(name)

def base_name(fn):
    core = fn
    if core.startswith("x_"): core = core[2:]
    elif core.startswith("x"): core = core[1:]
    return core.split("ǁ")[-1]

def baseline_for(fn):
    # original top-level name or class-method name
    short = base_name(fn)
    seg = of.get(fn) or of.get(short)
    if seg is None:
        seg = mf.get(fn) or mf.get(short)
    return seg

# For methods, mutant copy also defines _close_batch_for_size_limit at class level (baseline).
result = {}
miss = []
for fn, idxs in SURV.items():
    short = base_name(fn)
    base = of.get(fn) or of.get(short) or mf.get(short)
    for i in idxs:
        v = pick_variant(fn, i)
        if v is None:
            miss.append((fn,i)); continue
        d = [l for l in difflib.unified_diff(base.splitlines(), v.splitlines(), lineterm="", n=1)
             if l and (l.startswith(("-","+")) and not l.startswith(("---","+++")) or l.startswith("@@"))]
        key = f"{fn}__mutmut_{i}"
        result[key] = {"fn": fn, "idx": i, "diff": d}
json.dump({"res": result, "miss": miss}, open("/tmp/wp25/wp44-triage/_diffs_batch_agg.json","w"), indent=1)
print("extracted:", len(result), "missed:", len(miss), miss[:10], file=sys.stderr)
