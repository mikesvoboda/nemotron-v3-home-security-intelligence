import ast, json, difflib, sys, collections

path='/agents/agent-nemo2/workspace/mutants/backend/services/container_discovery.py'
src=open(path).read()
tree=ast.parse(src)

# map funcname -> (lineno, end_lineno) for top-level and class-nested defs
funcs={}
def walk(node):
    for n in ast.iter_child_nodes(node):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            seg=ast.get_source_segment(src, n)
            # dedent to normalize indentation for comparison
            funcs[n.name]=seg
        walk(n)
walk(tree)

meta=json.load(open('/agents/agent-nemo2/workspace/mutants/backend/services/container_discovery.py.meta'))
surv=sorted([k for k,v in meta['exit_code_by_key'].items() if v==0])

out=collections.defaultdict(list)  # signature -> keys
missing=[]
for k in surv:
    fn=k.split('.')[-1]  # e.g. x_build_configs_from_compose__mutmut_1
    orig=fn.replace('__mutmut_','__mutmut_orig_')[:-0] if False else None
    base=fn.rsplit('__mutmut_',1)[0]
    orig_name=base+'__mutmut_orig'
    if orig_name not in funcs or fn not in funcs:
        missing.append(k); continue
    a=funcs[orig_name].splitlines()
    b=funcs[fn].splitlines()
    # rename differing first line (def name) — normalize
    a[0]=a[0].replace('__mutmut_orig','')
    b[0]=b[0].replace(f'__mutmut_{fn.rsplit("__mutmut_",1)[1]}','')
    diff=[l for l in difflib.unified_diff(a,b,lineterm='',n=1) if l[:1] in '+-' and l[:3] not in ('---','+++')]
    sig=base+' || '+' ;; '.join(diff)
    out[sig].append(k)

print('missing:',len(missing), missing[:5])
print('clusters:',len(out))
# write results
res={'cluster_count':len(out),'clusters':[{'sig':s,'keys':ks} for s,ks in out.items()]}
json.dump(res,open('/tmp/wp25/wp44-triage/cd_clusters_raw.json','w'),indent=1)
# print compact view sorted by size
for s,ks in sorted(out.items(), key=lambda x:-len(x[1])):
    print(f"[{len(ks)}] {s[:300]}")
