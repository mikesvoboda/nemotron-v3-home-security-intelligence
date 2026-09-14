import ast, os, collections
ROOT="/agents/agent-nemo2/workspace/backend/tests"
HELPERS=["_get_base_database_url","_parse_database_url","_check_postgres_connection",
         "_drop_database_with_lock","_apply_schema_to_database","_ensure_clean_db","_reset_db_schema",
         "cleanup_stale_databases","template_database","worker_database"]
use=collections.defaultdict(list)
for dp,dn,fs in os.walk(ROOT):
    dn[:]=[d for d in dn if d!="__pycache__"]
    for fn in fs:
        if not fn.endswith(".py"): continue
        p=os.path.join(dp,fn); rel=os.path.relpath(p,ROOT)
        try: tree=ast.parse(open(p,encoding="utf-8").read(),filename=p)
        except SyntaxError: continue
        # only Name loads + attribute bases
        for n in ast.walk(tree):
            if isinstance(n,ast.Name) and n.id in HELPERS and isinstance(n.ctx,ast.Load):
                use[n.id].append((rel,n.lineno))
            if isinstance(n,ast.Attribute) and isinstance(n.value,ast.Name) and n.value.id in HELPERS:
                use[n.value.id].append((rel,n.lineno))
for h in HELPERS:
    hits=[x for x in use[h]]
    print("%-28s %d refs: %s" % (h,len(hits),sorted(set(hits))[:10]))
