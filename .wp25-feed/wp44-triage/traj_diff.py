import json, difflib, re, collections
SRC='/agents/agent-nemo2/workspace/mutants/backend/services/trajectory_analyzer.py'
LINES=open(SRC).read().split('\n')
spans=json.load(open('/agents/agent-nemo2/workspace/mutants/backend/services/trajectory_analyzer.py.spans'))['spans']
surv=json.load(open('/tmp/wp25/wp44-triage/_surv_traj.json'))

def block(name):
    if name not in spans: return None
    a,b=spans[name]
    return LINES[a-1:b]

out={}
missing=[]
for key in surv:
    tail=key.split('.')[-1]
    base,idx=tail.rsplit('__mutmut_',1)
    var=base+'__mutmut_'+idx
    orig=base+'__mutmut_orig'
    ml,ol=block(var),block(orig)
    if ml is None or ol is None:
        missing.append(key); continue
    f=lambda ls:[re.sub(r'__mutmut_\w+','N',l) for l in ls]
    d=[l for l in difflib.unified_diff(f(ol),f(ml),lineterm='',n=0)
       if l.startswith(('+','-')) and not l.startswith(('---','+++'))]
    out[key]=d
json.dump(out,open('/tmp/wp25/wp44-triage/_traj_diffs.json','w'))
print('survivors',len(surv),'diffed',len(out),'missing',len(missing),missing[:5])
# group identical diff-signature
sig=collections.defaultdict(list)
for k,d in out.items():
    sig[tuple(d)].append(k)
print('distinct diffs:',len(sig))
