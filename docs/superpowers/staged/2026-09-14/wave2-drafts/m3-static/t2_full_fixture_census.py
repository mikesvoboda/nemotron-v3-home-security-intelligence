import ast, os, json, collections
ROOT="/agents/agent-nemo2/workspace/backend/tests"
def is_fix(n):
    for d in n.decorator_list:
        t=d.func if isinstance(d,ast.Call) else d
        if (isinstance(t,ast.Attribute) and t.attr=="fixture") or (isinstance(t,ast.Name) and t.id=="fixture"): return True
    return False
defs=collections.defaultdict(list)
params=collections.defaultdict(list)
for dp,dn,fs in os.walk(ROOT):
    dn[:]=[d for d in dn if d!="__pycache__"]
    for fn in fs:
        if not fn.endswith(".py"): continue
        p=os.path.join(dp,fn); rel=os.path.relpath(p,ROOT)
        try: tree=ast.parse(open(p,encoding="utf-8").read(),filename=p)
        except SyntaxError: continue
        for n in ast.walk(tree):
            if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
                if is_fix(n): defs[n.name].append((rel,n.decorator_list[0].lineno,n.lineno,n.end_lineno))
                for a in n.args.args:
                    params[a.arg].append((rel,n.name,n.lineno))
# chaos conftest inventory
rows=[]
for name,dl in sorted(defs.items()):
    for (f,d,ln,en) in dl:
        if f=="chaos/conftest.py":
            cons=[c for c in params.get(name,[]) if not (c[0]=="chaos/conftest.py")]
            confself=[c for c in params.get(name,[]) if c[0]=="chaos/conftest.py"]
            rows.append((name,ln,en,len(cons),len(confself)))
print("chaos/conftest.py fixtures (name, def-line, end, external-consumers, conftest-internal-consumers):")
for r in rows: print("  %-34s %4d-%4d  ext=%d self=%d" % r)
print("TOTAL chaos fixtures:", len(rows))
# repo-wide conftest fixture stats for audit context
allnames=set(defs)
conffix={n for n,dl in defs.items() if any(d[0].endswith("conftest.py") for d in dl)}
print("unique fixture names tree-wide:", len(allnames))
