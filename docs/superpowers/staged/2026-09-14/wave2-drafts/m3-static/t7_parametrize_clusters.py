import ast, os
REPO="/agents/agent-nemo2/workspace/backend/tests"
CLASSES=[("unit/services/test_alert_dedup.py","TestValidateDedupKey",250,425),
         ("unit/services/test_xclip_loader.py","TestGetActionRiskWeight",1068,1167),
         ("unit/routes/test_system_routes.py","TestPipelineLatencyHistoryParameterValidation",4308,4400),
         ("unit/services/test_vision_extractor.py","TestYOLOFlorenceSemanticEquivalence",2173,2282),
         ("unit/services/test_mqtt_publisher.py","TestTopicMapping",111,224)]
def matches_of(fn):
    out=[]
    for n in ast.walk(fn):
        if isinstance(n,ast.Call):
            try: s=ast.unparse(n.func)
            except Exception: s=""
            if s=="pytest.raises":
                for kw in n.keywords:
                    if kw.arg=="match":
                        out.append(ast.unparse(kw.value))
                for a in n.args[1:]:
                    out.append("pos:"+ast.unparse(a))
    return out
for f,cls,lo,hi in CLASSES:
    p=os.path.join(REPO,f)
    if not os.path.exists(p): print("MISSING",f); continue
    src=open(p,encoding="utf-8").read(); tree=ast.parse(src)
    lines=src.splitlines()
    c=None
    for n in ast.walk(tree):
        if isinstance(n,ast.ClassDef) and n.name==cls: c=n
    if c is None: print("CLASS MISSING",cls,"in",f); continue
    meths=[m for m in c.body if isinstance(m,(ast.FunctionDef,ast.AsyncFunctionDef)) and m.name.startswith("test_")]
    rng=[m for m in meths if lo<=m.lineno<=hi]
    print("== %s :: %s  (class at %d-%d)  methods=%d (in-audit-range %d)" % (f,cls,c.lineno,c.end_lineno,len(meths),len(rng)))
    import collections
    bucket=collections.Counter()
    for m in meths:
        ms=matches_of(m)
        bucket[tuple(sorted(set(ms)))]+=1
    for k,v in bucket.most_common(6):
        print("     match-bucket %r x%d" % (k,v))
    # line span of methods
    print("     method lines: %d..%d (audit cited %d-%d)" % (min(m.lineno for m in meths), max(m.end_lineno for m in meths), lo, hi))
