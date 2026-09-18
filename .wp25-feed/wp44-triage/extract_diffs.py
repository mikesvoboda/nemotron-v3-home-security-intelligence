import json, re, difflib

MUT='/agents/agent-nemo2/workspace/mutants/backend/services/vision_extractor.py'
lines=open(MUT).read().split('\n')

def_re=re.compile(r'^(\s*)(?:async\s+)?def (\S+?)\s*[\(:]')
defs={}
for i,l in enumerate(lines):
    m=def_re.match(l)
    if m and '__mutmut_' in m.group(2):
        defs[m.group(2)]=(i, len(m.group(1)))

def body(name):
    i,ind=defs[name]
    # skip past signature: find first line after def ending with ':' at signature level
    j=i+1
    # the def line itself may end with ':' ; else advance until a line rstrip endswith ':' and next line is indented deeper or empty
    if not lines[i].rstrip().endswith(':'):
        while j<len(lines) and not lines[j].rstrip().endswith(':'):
            j+=1
        j+=1
    out=[]
    while j<len(lines):
        l=lines[j]
        if l.strip()=='':
            out.append(l); j+=1; continue
        cur=len(l)-len(l.lstrip())
        if cur<=ind: break
        out.append(l); j+=1
    while out and out[-1].strip()=='': out.pop()
    return out

meta=json.load(open('/agents/agent-nemo2/workspace/mutants/backend/services/vision_extractor.py.meta'))
surv=[k for k,v in meta['exit_code_by_key'].items() if v==0]

result=[]
for key in sorted(surv, key=lambda k:(k.split('__mutmut_')[0], int(k.split('__mutmut_')[-1]))):
    rest=key[len('backend.services.vision_extractor.'):]
    m=re.match(r'x(.+)__mutmut_(\d+)$', rest)
    fn, num = m.group(1), m.group(2)
    vname='x'+fn+'__mutmut_'+num
    oname='x'+fn+'__mutmut_orig'
    if vname not in defs or oname not in defs:
        result.append((fn,num,'MISSING')); continue
    ob=body(oname); vb=body(vname)
    sm=difflib.SequenceMatcher(None, ob, vb)
    changes=[]
    for tag,i1,i2,j1,j2 in sm.get_opcodes():
        if tag=='equal': continue
        o=' | '.join(s.strip() for s in ob[i1:i2])
        v=' | '.join(s.strip() for s in vb[j1:j2])
        changes.append((o,v))
    result.append((fn,num,changes))

with open('/tmp/wp25/wp44-triage/diffs.txt','w') as f:
    for fn,num,changes in result:
        if changes=='MISSING':
            f.write(f'### {fn} #{num} MISSING\n'); continue
        if not changes:
            f.write(f'### {fn} #{num} NO-DIFF (identical body)\n'); continue
        for o,v in changes:
            f.write(f'### {fn} #{num}\n- {o}\n+ {v}\n')
missing=[r for r in result if r[2]=='MISSING']
nodiff=[r for r in result if r[2]==[]]
print('total',len(result),'missing',len(missing),'nodiff',len(nodiff))
