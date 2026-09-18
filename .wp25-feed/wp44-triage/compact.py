import json, difflib, re, collections
BASE='backend.services.orchestrator.registry.'
spans=json.load(open('/agents/agent-nemo2/workspace/mutants/backend/services/orchestrator/registry.py.spans'))['spans']
src=open('/agents/agent-nemo2/workspace/mutants/backend/services/orchestrator/registry.py').read().split('\n')
meta=json.load(open('/agents/agent-nemo2/workspace/mutants/backend/services/orchestrator/registry.py.meta'))['exit_code_by_key']
def region(sp): return src[sp[0]:sp[1]+1]
def num(k): return int(k.rsplit('__mutmut_',1)[1])
surv=[k for k,v in meta.items() if v==0]
def fnname(k):
    m=k[len(BASE):]
    p=m.split('ǁ')
    if len(p)>=3: return p[1]+'.'+p[2].rsplit('__mutmut_',1)[0]
    return m.rsplit('__mutmut_',1)[0]
rows=[]
for k in surv:
    m=k[len(BASE):]
    s,e=spans[m]
    var='\n'.join(src[s:e+1])
    on=re.sub(r'__mutmut_\d+$','__mutmut_orig',m)
    os_,oe=spans[on]
    orig='\n'.join(src[os_:oe+1])
    minus=[];plus=[]
    for l in difflib.unified_diff(orig.split('\n'), var.split('\n'), lineterm='', n=0):
        if l.startswith('---') or l.startswith('+++') or l.startswith('@@'): continue
        if l.startswith('-'):
            t=l[1:].strip()
            if re.match(r'^(async )?def ', t): continue
            minus.append(t)
        elif l.startswith('+'):
            t=l[1:].strip()
            if re.match(r'^(async )?def ', t): continue
            plus.append(t)
    rows.append((fnname(k), num(k), ' || '.join(minus), ' || '.join(plus)))
rows.sort(key=lambda r:(r[0],r[1]))
with open('/tmp/wp25/wp44-triage/compact.txt','w') as f:
    for fn,n,a,b in rows:
        f.write(f'{fn}#{n}\t-{a}\t+{b}\n')
print('wrote', len(rows))
