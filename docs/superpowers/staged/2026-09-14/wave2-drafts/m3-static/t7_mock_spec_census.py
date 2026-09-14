import ast, os
REPO="/agents/agent-nemo2/workspace/backend/tests"
FILES=["unit/routes/test_system_routes.py","unit/services/test_nemotron_analyzer.py",
       "unit/routes/test_events_routes.py","unit/services/test_xclip_loader.py",
       "unit/core/test_database.py","unit/services/test_clip_client.py"]
MOCKS={"Mock","MagicMock","AsyncMock","PropertyMock"}
def has_spec(call):
    return any(k.arg in ("spec","spec_set","autospec") for k in call.keywords)
# resolve which paths exist
for f in FILES:
    p=os.path.join(REPO,f)
    if not os.path.exists(p):
        # search tree
        hits=[os.path.relpath(os.path.join(dp,fn),REPO) for dp,dn,fs in os.walk(REPO) for fn in fs if fn==os.path.basename(f) and "__pycache__" not in dp]
        print("PATH %s NOT FOUND; candidates: %s" % (f, hits)); continue
print()
for f in FILES:
    p=os.path.join(REPO,f)
    if not os.path.exists(p): continue
    src=open(p,encoding="utf-8").read(); tree=ast.parse(src); lines=src.splitlines()
    nmock=nospec=0; npatch=npatchautospec=0
    ex=[]
    for n in ast.walk(tree):
        if isinstance(n,ast.Call):
            fn=n.func
            nm = fn.id if isinstance(fn,ast.Name) else (fn.attr if isinstance(fn,ast.Attribute) else "")
            if nm in MOCKS:
                nmock+=1
                if not has_spec(n):
                    nospec+=1
                    if len(ex)<3: ex.append(n.lineno)
            if nm=="patch" or nm=="object" and isinstance(fn,ast.Attribute) and getattr(fn.value,"attr","")=="patch":
                pass
    # patch()/patch.object sites: count calls to mock.patch, patch, patch.object
    import re
    for m in re.finditer(r"patch(?:\.object)?\s*\(", src):
        npatch+=1
    autospec=len(re.findall(r"autospec\s*=\s*True", src))
    print("%-50s mocks=%4d unspecced=%4d  patch-sites=%4d autospec=True=%d   first unspecced lines: %s" % (f,nmock,nospec,npatch,autospec,ex))
