import re, json, difflib, sys

path='/agents/agent-nemo2/workspace/mutants/backend/services/orchestrator/models.py'
lines=open(path).read().split('\n')

# find def blocks
starts=[]
for i,l in enumerate(lines):
    m=re.match(r'^    def (.+?)(\(|$)', l)
    if m:
        starts.append((i, m.group(1)))
# end of each block = next def at same indent or line starting with 'mutants_'
bounds=[]
for idx,(i,name) in enumerate(starts):
    end=len(lines)
    for j in range(i+1,len(lines)):
        lj=lines[j]
        if re.match(r'^    def ',lj) or lj.startswith('mutants_') or lj.startswith('class ') or (lj and not lj.startswith(' ') and not lj.startswith('#')):
            end=j; break
    bounds.append((name,i,end))

bodies={name:'\n'.join(lines[i:end]) for name,i,end in bounds}

surv=[k.split('.models.',1)[1] for k in json.load(open('/agents/agent-nemo2/workspace/mutants/backend/services/orchestrator/models.py.meta'))['exit_code_by_key'].items() if False]
d=json.load(open('/agents/agent-nemo2/workspace/mutants/backend/services/orchestrator/models.py.meta'))
surv=sorted(k.split('.models.',1)[1] for k,v in d['exit_code_by_key'].items() if v==0)

out=open('/tmp/wp25/wp44-triage/manual-diffs.txt','w')
missing=[]
for s in surv:
    orig_fn=s.split('__mutmut_')[0]
    orig=bodies.get(orig_fn+'__mutmut_orig')
    var=bodies.get(s)
    if orig is None or var is None:
        missing.append(s); continue
    # normalize signature line diff noise: compare full blocks
    dl=list(difflib.unified_diff(orig.split('\n'), var.split('\n'), lineterm='', n=1))
    out.write('### '+s+'\n')
    out.write('\n'.join(dl[2:])+'\n\n')
out.close()
print('missing:',len(missing))
for m in missing[:10]: print('  ',m)
