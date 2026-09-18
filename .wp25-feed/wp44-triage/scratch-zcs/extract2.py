import json, re, ast, difflib

SRC='/agents/agent-nemo2/workspace/mutants/backend/services/zone_crossing_service.py'
text=open(SRC).read()
tree=ast.parse(text)
segs={}  # (qual, variant) -> source lines of body (excluding def line)

def walk(node, prefix):
    for ch in ast.walk(node) if False else []:
        pass

import itertools
def collect(node, cls_prefix):
    for ch in getattr(node,'body',[]):
        if isinstance(ch,(ast.FunctionDef,ast.AsyncFunctionDef)):
            m=re.match(r'(x.*?__mutmut)_(orig|\d+)', ch.name)
            if m:
                qual, var = m.group(1), m.group(2)
                # class prefix
                segs.setdefault((qual,var), []).append(('\n'.join(text.splitlines()[ch.lineno-1:ch.end_lineno])))
            collect(ch, cls_prefix)
        elif isinstance(ch, ast.ClassDef):
            collect(ch, ch.name)

collect(tree, '')

lines=text.splitlines()
def variant_src(qual,var):
    # find def node
    for m in re.finditer(r'(?:async )?def '+re.escape(qual)+r'_(?:orig|\d+)\(', text):
        pass
    return None

# simpler: redo with ast to get per-variant lineno/end_lineno
def find_defs(node):
    res=[]
    for ch in ast.walk(node):
        if isinstance(ch,(ast.FunctionDef,ast.AsyncFunctionDef)):
            m=re.match(r'(x.*?__mutmut)_(orig|\d+)$', ch.name)
            if m:
                qual,var=m.group(1),m.group(2)
                # body-only lines: from first stmt line to end_lineno, but decorators excluded; include def line stripped
                res.append((qual,var,ch.lineno,ch.end_lineno,ch.body[0].lineno if ch.body else ch.end_lineno))
    return res

defs=find_defs(tree)
blocks={}
for qual,var,ln0,end,bodystart in defs:
    blocks[(qual,var)]='\n'.join(lines[bodystart-1:end])

meta=json.load(open('/agents/agent-nemo2/workspace/mutants/backend/services/zone_crossing_service.py.meta'))
surv=[k for k,v in meta['exit_code_by_key'].items() if v==0]
out={}
miss=[]
for k in surv:
    tail=k.rsplit('.',1)[1]
    m=re.match(r'(x.*?__mutmut)_(\d+)',tail)
    qual,var=m.group(1),m.group(2)
    if (qual,var) not in blocks or (qual,'orig') not in blocks:
        miss.append(k); continue
    a=blocks[(qual,'orig')].splitlines()
    b=blocks[(qual,var)].splitlines()
    d=[dl for dl in difflib.unified_diff(a,b,lineterm='',n=1) if not dl.startswith(('---','+++','@@'))]
    fn=qual.replace('xǁ','').replace('ǁ','.')
    out.setdefault(fn,[]).append({'key':k,'diff':'\n'.join(d)})
json.dump(out,open('/tmp/wp25/wp44-triage/scratch-zcs/diffs2.json','w'),indent=1)
print('surv',len(surv),'extracted',sum(len(v) for v in out.values()),'missing',len(miss))
empty=sum(1 for v in out.values() for r in v if not r['diff'].strip())
print('empty diffs',empty)
