import ast, sys
def show(path, lineno, context=0):
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    lines = src.splitlines()
    # find enclosing func of lineno
    owners = [n for n in ast.walk(tree)
              if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.lineno <= lineno <= (n.end_lineno or n.lineno)]
    o = max(owners, key=lambda n: n.lineno) if owners else None
    print("="*72)
    print("SITE %s:%s  -> enclosing: %s (%s-%s)" % (path, lineno, o.name if o else "None", o.lineno if o else "-", o.end_lineno if o else "-"))
    if o:
        for i in range(o.lineno, min(o.end_lineno, len(lines)) + 1):
            has_assert = "assert" in lines[i-1]
            print("   %4d%s %s" % (i, "*" if has_assert else " ", lines[i-1][:110]))
for p, l in [("backend/tests/unit/services/test_pipeline_worker.py", 485),
             ("backend/tests/chaos/test_timeout_cascade.py", 198),
             ("backend/tests/chaos/test_timeout_cascade.py", 226),
             ("backend/tests/chaos/test_pubsub_failures.py", 325),
             ("backend/tests/integration/test_disaster_recovery.py", 262),
             ("backend/tests/unit/test_consolidated_fixtures.py", 59),
             ("backend/tests/unit/test_consolidated_fixtures.py", 306),
             ("backend/tests/unit/config/test_ab_rollout_production.py", 510)]:
    show(p, l)
