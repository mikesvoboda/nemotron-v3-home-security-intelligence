import ast, json, sys, re

MUT = "/agents/agent-nemo2/workspace/mutants/backend/services/zone_service.py"
ORIG = "/agents/agent-nemo2/workspace/backend/services/zone_service.py"

mut_src = open(MUT).read()
orig_src = open(ORIG).read()
mut_tree = ast.parse(mut_src)
orig_tree = ast.parse(orig_src)

def index(tree):
    d = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            d[node.name] = node
    return d

MF = index(mut_tree)
OF = index(orig_tree)

def dump(node):
    if node is None: return None
    return ast.dump(node, indent="")

def short(node):
    """body statements as unparse source lines"""
    if node is None: return []
    out=[]
    for s in node.body:
        try:
            out.append(ast.unparse(s))
        except Exception:
            out.append(ast.dump(s))
    return out

survivors = [l.strip() for l in open('/tmp/wp25/wp44-triage/survivors.txt') if l.strip()]
# survivors.txt first line is the count
if survivors[0].isdigit(): survivors = survivors[1:]
print("N survivors:", len(survivors))

results = {}
for key in survivors:
    mungled_num = key.split('.')[-1]           # x_foo__mutmut_19
    m = re.match(r'^(.*)__mutmut_(\d+)$', mungled_num)
    base, num = m.group(1), m.group(2)
    real = base[1:] if base.startswith('x') else base   # strip single leading 'x'
    mnode = MF.get(mungled_num)
    onode = MF.get(base + '__mutmut_orig') or OF.get(real)
    if mnode is None:
        print("MISSING MUTANT", key); continue
    mb = short(mnode); ob = short(onode)
    diffs = [(i, o, n) for i,(o,n) in enumerate(zip(ob, mb)) if o != n]
    results[key] = {
        'func': real,
        'num': int(num),
        'orig_body_len': len(ob), 'mut_body_len': len(mb),
        'diffs': diffs,
        'mut_body': mb,
    }

json.dump({k:{kk:vv for kk,vv in v.items()} for k,v in results.items()}, open('/tmp/wp25/wp44-triage/diffs.json','w'), indent=1)

# print compact report
for key in survivors:
    r = results[key]
    print("="*100)
    print(key, " func=%s"%r['func'], " len orig=%d mut=%d"%(r['orig_body_len'], r['mut_body_len']))
    if r['orig_body_len'] != r['mut_body_len']:
        print("  !! STATEMENT COUNT DIFFERS")
    for i,o,n in r['diffs']:
        print("  [@%d] ORIG: %s"%(i,o))
        print("       MUT : %s"%n)
