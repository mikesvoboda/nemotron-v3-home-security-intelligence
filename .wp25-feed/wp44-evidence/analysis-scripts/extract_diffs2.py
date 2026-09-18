import re, difflib, json

MUT='/agents/agent-nemo2/workspace/mutants/backend/api/routes/gpu_config.py'
lines=open(MUT).read().split('\n')

starts=[]
for i,l in enumerate(lines):
    m=re.match(r'^(?:async )?def (x__\w+?)__mutmut_(\w+)\(', l)
    if m:
        starts.append((m.group(1), m.group(2), i))

bodies={}
for idx,(fn,num,st) in enumerate(starts):
    end=len(lines)
    if idx+1<len(starts):
        end=starts[idx+1][2]
    # cut body at the registry assignment line
    body=[]
    for l in lines[st:end]:
        if l.startswith('mutants_'):
            break
        body.append(l)
    bodies[(fn,num)]=body

survivors=json.load(open('/tmp/wp25/survivors.json'))
out=[]
for key in survivors:
    base, num = key.split('.x_')[-1], key.split('__mutmut_')[1]
    # fn name = everything before __mutmut_ minus the leading x_
    fn = base if base.startswith('x__') else 'x__'+base.split('.x__')[-1]
    # simpler: derive from key
    keystem = key[len('backend.api.routes.gpu_config.'):]
    fn = keystem.split('__mutmut_')[0]
    a=bodies.get((fn,'orig'))
    b=bodies.get((fn,num))
    if a is None or b is None:
        out.append((key,'MISSING orig=%s var=%s'%(a is not None,b is not None),''))
        continue
    d=list(difflib.unified_diff(a,b,lineterm='',n=0))
    changes=[l for l in d if l.startswith(('+','-')) and not l.startswith(('+++','---'))]
    out.append((key,fn,'\n'.join(changes)))

with open('/tmp/wp25/gpu_config_diffs.txt','w') as f:
    for key,fn,ch in out:
        f.write('### '+key+'\n')
        f.write((ch or '(NO DIFF)')+'\n')
print('missing:',sum(1 for _,f,_ in out if f=='MISSING' or 'MISSING' in f))
print('nodiff:',sum(1 for _,_,c in out if c=='(NO DIFF)'))
