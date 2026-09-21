import json, re, ast, difflib, sys

MUT = "/agents/agent-nemo2/workspace/mutants/backend/services/florence_client.py"
ORIG = "/agents/agent-nemo2/workspace/backend/services/florence_client.py"

d = json.load(open("/agents/agent-nemo2/workspace/mutants/backend/services/florence_client.py.meta"))
surv = sorted([k for k,v in d["exit_code_by_key"].items() if v == 0],
              key=lambda k: (k.split("ǁ")[1] if "ǁ" in k else k, int(k.rsplit("_",1)[1])))

mut_src = open(MUT).read()
orig_src = open(ORIG).read()

print("parsing mutant file (%d bytes)..." % len(mut_src), file=sys.stderr)
mtree = ast.parse(mut_src)
otree = ast.parse(orig_src)

mfun = {}
for node in ast.walk(mtree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        seg = ast.get_source_segment(mut_src, node)
        if seg is not None:
            mfun.setdefault(node.name, seg)

ofun = {}
for node in ast.walk(otree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        seg = ast.get_source_segment(orig_src, node)
        if seg is not None:
            ofun.setdefault(node.name, seg)

def variant_name(key):
    # backend.services.florence_client.xǁFlorenceClientǁ__init____mutmut_14
    return key.split("florence_client.", 1)[1]

def baseline_for(vname):
    base = vname.rsplit("__mutmut_", 1)[0] + "__mutmut_orig"
    if base in mfun:
        return mfun[base], "mutorig"
    # top-level original name
    short = vname[1:].split("ǁ")[-1]
    if short in ofun:
        return ofun[short], "orig"
    return mfun.get(short), "mfunshort"

result = {}
miss = []
for k in surv:
    vname = variant_name(k)
    v = mfun.get(vname)
    if v is None:
        miss.append(("novariant", k)); continue
    b, how = baseline_for(vname)
    if b is None:
        miss.append(("nobase", k)); continue
    dl = [l for l in difflib.unified_diff(b.splitlines(), v.splitlines(), lineterm="", n=0)
          if l and ((l.startswith(("-","+")) and not l.startswith(("---","+++"))) or l.startswith("@@"))]
    result[k] = {"fn": vname, "base": how, "diff": dl}

json.dump({"res": result, "miss": miss, "n_surv": len(surv), "n_res": len(result)},
          open("/tmp/wp25/wp44-triage/_fl_diffs.json","w"), indent=1)
print("survivors", len(surv), "extracted", len(result), "missed", len(miss), file=sys.stderr)
for m in miss[:20]: print("MISS", m, file=sys.stderr)
