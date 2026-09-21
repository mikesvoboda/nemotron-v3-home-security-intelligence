import json, re, difflib
MF='mutants/backend/services/batch_aggregator.py'
src=open(MF,encoding='utf-8').read().splitlines()
defre=re.compile(r'^(\s*)(?:async\s+)?def\s+(x\S+?__mutmut_(?:orig|\d+))\s*\(')
defs=[(i,m.group(2)) for i,l in enumerate(src) if (m:=defre.match(l))]
blocks={}
for j,(s,n) in enumerate(defs):
    e=defs[j+1][0] if j+1<len(defs) else len(src)
    b=src[s:e]
    for k,l in enumerate(b):
        if l.startswith('mutants_'): b=b[:k]; break
    blocks[n]=b
def fam(n): return n.rsplit('__mutmut_',1)[0]
def sdl(body):
    out=[];started=False;depth=0
    for l in body:
        if not started:
            depth+=l.count('(')-l.count(')')
            if depth<=0 and l.rstrip().endswith(':'): started=True
            continue
        out.append(l)
    while out and not out[-1].strip(): out.pop()
    return out
clusters=json.load(open('/tmp/wp25/wp44-triage/clusters.json'))
def delta(key):
    tail=key.rsplit('.',1)[-1]; f=fam(tail)
    ob=sdl(blocks[f+'__mutmut_orig']); vb=sdl(blocks[tail])
    fr=[]
    for tag,i1,i2,j1,j2 in difflib.SequenceMatcher(None,ob,vb).get_opcodes():
        if tag=='equal': continue
        fr.append((' | '.join(x.strip() for x in ob[i1:i2]))[:120]+' ==> '+(' | '.join(x.strip() for x in vb[j1:j2]))[:120])
    return ' ;; '.join(fr)
outf=open('/tmp/wp25/wp44-triage/reps.txt','w')
for ck,ks in clusters.items():
    f,role,kind,kt=ck.split('|')
    outf.write(f'\n### {ck}  n={len(ks)}  keys={ks[:3]}\n')
    for key in ks[:2]:
        outf.write('    '+delta(key)+'\n')
outf.close()
