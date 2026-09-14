import ast
SITES = [
 ("backend/tests/unit/models/test_api_key_model.py", 323),
 ("backend/tests/unit/models/test_job_transition.py", 101),
 ("backend/tests/unit/models/test_job_log.py", 105),
 ("backend/tests/unit/models/test_job_attempt.py", 106),
 ("backend/tests/unit/models/test_user_model.py", 385),
 ("backend/tests/unit/services/test_enrichment_classification_errors.py", 621),
 ("backend/tests/unit/services/test_enrichment_classification_errors.py", 660),
 ("backend/tests/unit/services/test_enrichment_classification_errors.py", 695),
 ("backend/tests/unit/services/test_job_tracker.py", 567),
 ("backend/tests/unit/services/test_job_tracker.py", 749),
 ("backend/tests/integration/test_job_tracker.py", 567),
 ("backend/tests/integration/test_job_tracker.py", 749),
]
def counts(fn):
    a=r=w=s=0
    for n in ast.walk(fn):
        if isinstance(n, ast.Assert): a+=1
        if isinstance(n, ast.Call):
            try: s_=ast.unparse(n.func)
            except Exception: s_=""
            if s_=="pytest.raises": r+=1
            elif s_=="pytest.warns": w+=1
            elif "skip" in s_ or "xfail" in s_: s+=1
    return a,r,w,s
for p,l in SITES:
    try: src=open(p,encoding="utf-8").read()
    except FileNotFoundError:
        print("MISSING %s" % p); continue
    tree=ast.parse(src)
    funcs=sorted([n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name.startswith("test_")],key=lambda n:n.lineno)
    o=None
    for f in funcs:
        if f.lineno<=l<=(f.end_lineno or f.lineno): o=f
    if o is None:
        prec=[f for f in funcs if f.lineno<l]
        o=prec[-1] if prec else None
    if o is None:
        print("%s:%d -> no enclosing/nearby test" % (p,l)); continue
    a,r,w,sk=counts(o)
    doc=(ast.get_docstring(o) or "")[:80]
    print("%s:%d -> %s@%d asserts=%d raises=%d warns=%d skip/xfail-markers-in-body=%d :: %s" % (p,l,o.name,o.lineno,a,r,w,sk,doc))
