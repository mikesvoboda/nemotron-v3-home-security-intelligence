import re, sys, difflib, json, collections

MUT='/agents/agent-nemo2/workspace/mutants/backend/services/cost_tracker.py'
SRC=open(MUT).read().split('\n')

# find function blocks: lines starting with 'def ' or indented '    def '
funcs={}  # full_name -> list of source lines
cur=None
start=None
for i,l in enumerate(SRC):
    m=re.match(r'^(\s*)(?:async )?def (\S+)\(', l)
    if m:
        indent=len(m.group(1))
        name=m.group(2)
        if cur is not None:
            funcs[cur]=(SRC[start:i])
        cur=name
        funcs[cur+'__INDENT__']=indent
        start=i
if cur is not None:
    funcs[cur]=SRC[start:]

def body(name):
    lines=funcs.get(name)
    if lines is None: return None
    return lines

surv=[s.strip() for s in open('/tmp/wp25/wp44-triage/survivor_keys_cost_tracker.txt') if s.strip()]
out=open('/tmp/wp25/wp44-triage/survivor_diffs.txt','w')
missing=[]
for key in surv:
    tail=key.split('.')[-1]
    # tail like xǁCostTrackerǁtrack_enrichment_usage__mutmut_2
    base, idx = tail.rsplit('__mutmut_',1)
    mutname=base+'__mutmut_'+idx
    origname=base+'__mutmut_orig'
    ml=body(mutname); ol=body(origname)
    if ml is None or ol is None:
        missing.append(key); continue
    # strip def-line differences (the clobbered name appears in the def line)
    ml2=[re.sub(r'__mutmut_\w+','NAME',l) for l in ml]
    ol2=[re.sub(r'__mutmut_\w+','NAME',l) for l in ol]
    d=list(difflib.unified_diff(ol2,ml2,lineterm='',n=1))
    d=[l for l in d if not l.startswith(('---','+++','@@')) ]
    d=[l for l in d if l.startswith(('-','+'))]
    out.write(key+' :: '+'\n'.join(d)+'\n----\n')
out.close()
print('missing:',missing[:5], 'count', len(missing))
