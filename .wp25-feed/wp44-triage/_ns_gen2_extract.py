import ast, json, re, sys, difflib
from collections import defaultdict

P = "/agents/agent-nemo2/workspace/mutants/backend/services/nemotron_streaming.py"
meta = json.load(open("/agents/agent-nemo2/workspace/mutants/backend/services/nemotron_streaming.py.meta"))
ebk = meta["exit_code_by_key"]

src = open(P).read()
tree = ast.parse(src)

funcs = {}
for node in tree.body:
    if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
        funcs[node.name] = node

# orig bodies
orig = {}
for name, node in funcs.items():
    if name.endswith("__mutmut_orig"):
        base = name[:-len("__mutmut_orig")]
        orig[base] = node

def body_dump(node):
    # dedented source of body statements
    seg = ast.get_source_segment(src, node)
    return seg

out = {}
missing = []
for key, code in ebk.items():
    m = re.match(r"^(.+)__mutmut_(\d+)$", key)
    if not m:
        missing.append(key); continue
    base = m.group(1)  # e.g. backend.services.nemotron_streaming.x_call_llm_streaming
    fname = base.split(".")[-1]
    mut_name = fname + "__mutmut_" + m.group(2)
    oname = fname + "__mutmut_orig"
    if mut_name not in funcs or oname not in funcs:
        missing.append(key); continue
    o_src = body_dump(funcs[oname])
    m_src = body_dump(funcs[mut_name])
    out[key] = {
        "exit": code,
        "fn": fname,
        "diff": list(difflib.unified_diff(o_src.splitlines(), m_src.splitlines(), lineterm="", n=0)),
    }

json.dump(out, open("/tmp/wp25/wp44-triage/_ns_gen2_diffs.json", "w"))
print("mutants parsed:", len(out), "missing:", len(missing))
if missing[:5]: print("sample missing:", missing[:5])
surv = [k for k,v in out.items() if v["exit"]==0]
print("survivors:", len(surv))
# how many survivors have empty diff (equivalent/suspicious)?
empty = [k for k in surv if not [l for l in out[k]["diff"] if l.startswith(("+","-")) and not l.startswith(("+++","---"))]]
print("survivors with empty diff:", len(empty))
