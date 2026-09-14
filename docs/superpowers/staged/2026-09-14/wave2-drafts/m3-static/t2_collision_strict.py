import ast, os, collections
ROOT="/agents/agent-nemo2/workspace/backend/tests"
TARGETS=("session","mock_redis")
def is_fix(n):
    for d in n.decorator_list:
        t=d.func if isinstance(d,ast.Call) else d
        if (isinstance(t,ast.Attribute) and t.attr=="fixture") or (isinstance(t,ast.Name) and t.id=="fixture"): return True
    return False
def test_or_fixture_funcs(tree):
    """top-level funcs + class methods only (not nested defs)"""
    out=[]
    for n in ast.iter_child_nodes(tree):
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
            if n.name.startswith("test_") or is_fix(n): out.append(n)
        elif isinstance(n,ast.ClassDef):
            for m in ast.iter_child_nodes(n):
                if isinstance(m,(ast.FunctionDef,ast.AsyncFunctionDef)) and (m.name.startswith("test_") or is_fix(m)):
                    out.append(m)
    return out
conftests={}
for dp,dn,fs in os.walk(ROOT):
    dn[:]=[d for d in dn if d!="__pycache__"]
    if "conftest.py" in fs:
        p=os.path.join(dp,"conftest.py")
        tree=ast.parse(open(p,encoding="utf-8").read(),filename=p)
        conftests[os.path.relpath(dp,ROOT)]={n.name for n in test_or_fixture_funcs(tree) if is_fix(n)} | {n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and is_fix(n)}
def resolve(rel,name):
    d=os.path.dirname(rel) or "."
    d="." if d=="" else d
    cur=d
    while True:
        key=cur
        if key in conftests and name in conftests[key]:
            return "conftest:"+cur if cur!="." else "conftest:ROOT"
        if cur==".": break
        parent=os.path.dirname(cur)
        if parent==cur: break
        cur=parent or "."
        if not os.path.isdir(os.path.join(ROOT,cur)): cur="."
    return "UNRESOLVED"
agg=collections.defaultdict(list)
for dp,dn,fs in os.walk(ROOT):
    dn[:]=[d for d in dn if d!="__pycache__"]
    for fn in sorted(fs):
        if not fn.endswith(".py"): continue
        p=os.path.join(dp,fn); rel=os.path.relpath(p,ROOT)
        try: tree=ast.parse(open(p,encoding="utf-8").read(),filename=p)
        except SyntaxError: continue
        # module-local fixture defs shadow conftest
        local_fixes={n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and is_fix(n)}
        for f in test_or_fixture_funcs(tree):
            for a in f.args.args:
                if a.arg in TARGETS:
                    if a.arg in local_fixes and rel!="conftest.py" and os.path.basename(rel)!="conftest.py":
                        tgt="module-local:"+rel
                    elif os.path.basename(rel)=="conftest.py" and a.arg in local_fixes:
                        tgt="self-conftest:"+rel
                    else:
                        tgt=resolve(rel,a.arg)
                    agg[(a.arg,tgt)].append((rel,f.name,f.lineno))
for (t,tgt),hits in sorted(agg.items()):
    if tgt=="conftest:ROOT" or (t in tgt):
        print("%-10s -> %-40s %d real consumer sites" % (t,tgt,len(hits)))
        for h in hits[:12]: print("     %s :: %s @%d" % h)
    elif tgt!="conftest:integration":
        pass
print()
print("== totals by resolution ==")
tot=collections.Counter()
for (t,tgt),hits in agg.items(): tot[(t,tgt)]+=len(hits)
for k,v in sorted(tot.items()):
    print("%s %s: %d" % (k[0],k[1],v))
