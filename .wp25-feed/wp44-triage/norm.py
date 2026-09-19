import ast, json, re, difflib, collections

MUT='/agents/agent-nemo2/workspace/mutants/backend/services/plate_detector.py'
src=open(MUT).read()
tree=ast.parse(src)
funcs={}
for node in ast.walk(tree):
    if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
        s=ast.get_source_segment(src,node)
        if s: funcs.setdefault(node.name,s)

groups=collections.defaultdict(dict)
pat=re.compile(r'^(?P<base>.+)__mutmut_(?P<num>orig|\d+)$')
for name,s in funcs.items():
    m=pat.match(name)
    if m: groups[m.group('base')][m.group('num')]=s

out={}
for base,variants in groups.items():
    orig=variants.get('orig')
    if orig is None: continue
    norm_orig=orig.replace(base+'__mutmut_orig','FN')
    for num,body in variants.items():
        if num=='orig': continue
        nb=body.replace(base+f'__mutmut_{num}','FN')
        if nb==norm_orig:
            out[f'{base}|{num}']=['<NO-VISIBLE-DIFF>']
            continue
        d=[l for l in difflib.unified_diff(norm_orig.splitlines(),nb.splitlines(),lineterm='',n=1)
           if l.startswith(('+','-')) and not l.startswith(('+++','---'))]
        out[f'{base}|{num}']=d
json.dump(out,open('/tmp/wp25/wp44-triage/alldiffs.json','w'),indent=1)

meta=json.load(open('/agents/agent-nemo2/workspace/mutants/backend/services/plate_detector.py.meta'))
surv=[k for k,v in meta['exit_code_by_key'].items() if v==0]
print('bases found:',sorted(groups.keys()))
for k in sorted(surv, key=lambda x:(x.split('.')[-1].rsplit('__mutmut_',1)[0], int(x.rsplit('__mutmut_',1)[1]))):
    fn=k.split('.')[-1].rsplit('__mutmut_',1)[0]; n=k.rsplit('__mutmut_',1)[1]
    d=out.get(f'{fn}|{n}')
    print('###',k)
    if d is None: print('   MISSING')
    else:
        for l in d: print('   ',l)
