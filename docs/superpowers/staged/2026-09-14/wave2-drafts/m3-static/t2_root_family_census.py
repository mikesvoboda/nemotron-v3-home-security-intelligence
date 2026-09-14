import ast, os, collections
ROOT="/agents/agent-nemo2/workspace/backend/tests"
TARGETS=("isolated_db","test_db","session","mock_redis","mock_db_session","integration_env")
def is_fix(n):
    for d in n.decorator_list:
        t=d.func if isinstance(d,ast.Call) else d
        if (isinstance(t,ast.Attribute) and t.attr=="fixture") or (isinstance(t,ast.Name) and t.id=="fixture"): return True
    return False
def tops(tree):
    out=[]
    for n in ast.iter_child_nodes(tree):
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
            if n.name.startswith("test_") or is_fix(n): out.append(n)
        elif isinstance(n,ast.ClassDef):
            for m in ast.iter_child_nodes(n):
                if isinstance(m,(ast.FunctionDef,ast.AsyncFunctionDef)) and (m.name.startswith("test_") or is_fix(m)): out.append(m)
    return out
def resolve(rel,name,local_fixes):
    if name in local_fixes and os.path.basename(rel)!="conftest.py": return "module-local"
    cur=os.path.dirname(rel) or "."
    while True:
        cp=os.path.join(ROOT,cur,"conftest.py") if cur!="." else os.path.join(ROOT,"conftest.py")
        if os.path.exists(cp):
            t=ast.parse(open(cp,encoding="utf-8").read())
            names={n.name for n in ast.walk(t) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and is_fix(n)}
            if name in names: return "conftest:"+ (cur or "ROOT")
        if cur==".": break
        p=os.path.dirname(cur) or "."
        if p==cur: break
        cur=p if os.path.isdir(os.path.join(ROOT,cur if cur!="." else "")) else "."
        if not os.path.isdir(os.path.join(ROOT,cur)): cur="."
    return "UNRESOLVED"
res=collections.defaultdict(collections.Counter)
detail=collections.defaultdict(list)
for dp,dn,fs in os.walk(ROOT):
    dn[:]=[d for d in dn if d!="__pycache__"]
    for fn in sorted(fs):
        if not fn.endswith(".py"): continue
        p=os.path.join(dp,fn); rel=os.path.relpath(p,ROOT)
        try: tree=ast.parse(open(p,encoding="utf-8").read())
        except SyntaxError: continue
        local={n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and is_fix(n)}
        for f in tops(tree):
            for a in f.args.args:
                if a.arg in TARGETS:
                    r=resolve(rel,a.arg,local)
                    res[a.arg][r if not r.startswith("module") else "module-local:"+rel]+=1
                    if r=="conftest:ROOT": detail[a.arg].append((rel,f.name,f.lineno))
for t in TARGETS:
    print("%-16s %s" % (t, dict(res[t])))
    if detail[t]:
        for d in detail[t][:14]: print("     ROOT %s :: %s @%d" % d)
