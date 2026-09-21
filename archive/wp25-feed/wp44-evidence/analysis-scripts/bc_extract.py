import ast, json, difflib

ORIG = "/agents/agent-nemo2/workspace/backend/services/batch_coalescer.py"
COPY = "/agents/agent-nemo2/workspace/mutants/backend/services/batch_coalescer.py"
META = "/agents/agent-nemo2/workspace/mutants/backend/services/batch_coalescer.py.meta"
sep = "ǁ"

def parse_funcs(path):
    src = open(path).read()
    lines = src.splitlines()
    funcs = {}
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        start = node.body[0].lineno
        if isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) \
           and isinstance(node.body[0].value.value, str):
            start = node.body[0].end_lineno + 1
            if len(node.body) < 2:
                start = node.body[0].end_lineno  # docstring-only fn: whole body
        code = [l.strip() for l in lines[start-1:node.end_lineno] if l.strip()]
        funcs[node.name] = code
    return funcs

orig_funcs = parse_funcs(ORIG)
copy_funcs = parse_funcs(COPY)

ebk = json.load(open(META))["exit_code_by_key"]
survivors = sorted([k for k, v in ebk.items() if v == 0])

report = []
for key in survivors:
    mangled = key.split(".")[-1]
    parts = mangled.split(sep)
    func_part = parts[2].rsplit("__mutmut_", 1)[0]
    o = orig_funcs.get(func_part)
    v = copy_funcs.get(mangled)
    if o is None or v is None:
        report.append((key, "EXTRACT-FAIL", "", ""))
        continue
    sm = difflib.SequenceMatcher(None, o, v, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        report.append((key, tag, " ; ".join(o[i1:i2]), " ; ".join(v[j1:j2])))

fn_of = lambda k: k.split("ǁ")[-1].rsplit("__mutmut_", 1)[0]
num_of = lambda k: k.rsplit("_", 1)[1]
prev = None
for key, tag, o, v in report:
    label = f"{fn_of(key)}#{num_of(key)}"
    if tag == "EXTRACT-FAIL":
        print(f"{label}: EXTRACT-FAIL"); continue
    if tag == "delete":
        print(f"{label}: -[{o}]")
    elif tag == "insert":
        print(f"{label}: +[{v}]")
    else:
        print(f"{label}: -[{o}] +[{v}]")
    if label != prev and False: pass
    prev = label
with open("/tmp/wp25/bc_survivor_deltas.txt", "w") as f:
    for key, tag, o, v in report:
        f.write(f"{key}\t{tag}\t{o}\t{v}\n")
print("total delta hunks:", len(report))
