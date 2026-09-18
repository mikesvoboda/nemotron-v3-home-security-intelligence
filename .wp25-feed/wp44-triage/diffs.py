import json, difflib, sys, re

BASE='backend.services.orchestrator.registry.'
spans=json.load(open('/agents/agent-nemo2/workspace/mutants/backend/services/orchestrator/registry.py.spans'))['spans']
src=open('/agents/agent-nemo2/workspace/mutants/backend/services/orchestrator/registry.py').read().split('\n')
meta=json.load(open('/agents/agent-nemo2/workspace/mutants/backend/services/orchestrator/registry.py.meta'))['exit_code_by_key']

def region(span):
    s,e=span
    return src[s:e+1]

def diff_for(mangled):
    if mangled not in spans: return None
    s,e=spans[mangled]
    var='\n'.join(src[s:e+1])
    orig_name=re.sub(r'__mutmut_\d+$','__mutmut_orig',mangled)
    if orig_name not in spans: return ('NO_ORIG', var)
    os_,oe=spans[orig_name]
    orig='\n'.join(src[os_:oe+1])
    d=[l for l in difflib.unified_diff(orig.split('\n'), var.split('\n'), lineterm='', n=1)]
    return '\n'.join(d)

surv=[k for k,v in meta.items() if v==0]
def num(k): return int(k.rsplit('__mutmut_',1)[1])
surv.sort(key=lambda k:(k.rsplit('__mutmut_',1)[0], num(k)))
out=[]
for k in surv:
    mangled=k[len(BASE):]
    d=diff_for(mangled)
    out.append('==== '+mangled)
    out.append(d if isinstance(d,str) else str(d))
open('/tmp/wp25/wp44-triage/diffs_all.txt','w').write('\n'.join(out))
print('survivors', len(surv))
print('\n'.join(out[:60]))
