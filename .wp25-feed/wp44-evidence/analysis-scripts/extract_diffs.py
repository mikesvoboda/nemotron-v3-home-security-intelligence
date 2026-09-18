import re, sys, difflib, json

MUT='/agents/agent-nemo2/workspace/mutants/backend/api/routes/gpu_config.py'
lines=open(MUT).read().split('\n')

# find def boundaries
defs=[]  # (name, start, end)
for i,l in enumerate(lines):
    m=re.match(r'^def (x__\w+?)__mutmut_(\w+)\(', l)
    if m:
        defs.append((m.group(1), m.group(2), i))
for idx,(fn,num,st) in enumerate(defs):
    end=defs[idx+1][2] if idx+1<len(defs) else len(lines)
    # trim trailing blank lines
    defs[idx]=(fn,num,st,end)

bodies={}
for fn,num,st,end in defs:
    body=lines[st+1:end]
    # drop decorator/preceding blanks: keep as is
    bodies[(fn,num)]=body

survivors=json.load(open('/tmp/wp25/survivors.json'))
out=[]
for key in survivors:
    fn,num=key.split('__mutmut_')[0].split('.')[-1], key.split('__mutmut_')[1]
    a=bodies.get((fn,'orig'))
    b=bodies.get((fn,num))
    if a is None or b is None:
        out.append((key,'MISSING',''))
        continue
    # indent-strip
    d=list(difflib.unified_diff(a,b,lineterm='',n=1))
    changes=[l for l in d if l.startswith(('+','-')) and not l.startswith(('+++','---'))]
    out.append((key,fn,'\n'.join(changes)))

with open('/tmp/wp25/gpu_config_diffs.txt','w') as f:
    for key,fn,ch in out:
        f.write('='*10+' '+key+'\n')
        f.write((ch or '(no textual diff — identical body)')+'\n')
print('done',len(out))
