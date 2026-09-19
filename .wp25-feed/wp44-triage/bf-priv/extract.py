import json, re, difflib
base='/agents/agent-nemo2/workspace'
lines=open(base+'/mutants/backend/services/batch_fetch.py').read().split('\n')
# find start lines of defs at col 0
defs={}
starts=[]
for i,l in enumerate(lines):
    m=re.match(r'^(?:async )?def ((?:x_)?[A-Za-z_0-9ǁ]*)\s*\(', l)
    if m:
        defs[m.group(1)]=i
        starts.append(i)
    elif re.match(r'^(mutants_|\[)', l):
        starts.append(i)
starts.sort()
def block(name):
    i=defs[name]
    # end = next boundary line after i
    for s in starts:
        if s>i:
            return '\n'.join(lines[i:s]).rstrip()
    return '\n'.join(lines[i:]).rstrip()

keys=[l.strip() for l in open('/tmp/wp25/wp44-triage/bf-priv/keys.txt') if l.strip()]
out=[]
for k in keys:
    vname=k.split('batch_fetch.',1)[-1]
    oname=vname.rsplit('__mutmut_',1)[0]+'__mutmut_orig'
    if vname not in defs or oname not in defs:
        out.append((k,'EXTRACTION_FAIL v=%s o=%s'%(vname in defs, oname in defs)));continue
    # normalize names so def-line rename isn't shown as diff
    norm=lambda t: t.replace(vname,'FN').replace(oname,'FN')
    d=list(difflib.unified_diff(norm(block(oname)).split('\n'), norm(block(vname)).split('\n'), lineterm='', n=2))
    body='\n'.join(d)
    if not d: body='<<IDENTICAL TO ORIG>>'
    out.append((k,body))
with open('/tmp/wp25/wp44-triage/bf-priv/diffs.txt','w') as f:
    for k,b in out:
        f.write('##### '+k+'\n'+b+'\n')
for k,b in out:
    print('##### '+k); print(b)
