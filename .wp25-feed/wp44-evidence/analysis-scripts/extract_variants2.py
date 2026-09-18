import re, difflib, json, sys

COPY='/agents/agent-nemo2/workspace/mutants/backend/services/pg_notify_listener.py'
src=[l.rstrip('\n') for l in open(COPY)]

pat=re.compile(r'^(\s*)(?:async\s+)?def (x\S*__mutmut(?:_orig|_\d+))\s*[\(:]')
starts=[(m.group(2),i) for i,l in enumerate(src) if (m:=pat.match(l))]

# also record where each REAL (decorated) method starts so we can truncate blocks at it
texts={}
for idx,(name,st) in enumerate(starts):
    en = starts[idx+1][1] if idx+1<len(starts) else len(src)
    # truncate at first line after st+1 that is a decorator '@_mutmut_mutated' at same indent as st's def (i.e., a real method following)
    ind=len(src[st])-len(src[st].lstrip())
    for j in range(st+1,en):
        l=src[j]
        if l.strip().startswith('@_mutmut_mutated') and (len(l)-len(l.lstrip()))==ind:
            en=j; break
        if l.strip().startswith('mutants_') and (len(l)-len(l.lstrip()))<=ind:
            en=j; break
    body=[l.strip() for l in src[st:en] if l.strip()]  # strip whitespace for diffing
    texts[name]=body

print("TOTAL_BLOCKS", len(texts), file=sys.stderr)
meta=json.load(open('/agents/agent-nemo2/workspace/mutants/backend/services/pg_notify_listener.py.meta'))
surv=sorted(k for k,v in meta['exit_code_by_key'].items() if v==0)

out=[]
for key in surv:
    vname=key.split('.')[-1]
    orig_name=vname.rsplit('__mutmut',1)[0]+'__mutmut_orig'
    a=[l.replace(orig_name,'FN') for l in texts[orig_name]]
    b=[l.replace(vname,'FN') for l in texts[vname]]
    diff=[l for l in difflib.unified_diff(a,b,lineterm='',n=0) if l.startswith(('+','-')) and not l.startswith(('+++','---'))]
    out.append((key,diff))

with open('/tmp/wp25/pgnl_diffs2.txt','w') as f:
    for key,diff in out:
        f.write(f'### {key}\n'+'\n'.join(diff)+'\n\n')
empty=[k for k,d in out if not [x for x in d if x[1:].strip()]]
print("EMPTY:",empty, file=sys.stderr)
