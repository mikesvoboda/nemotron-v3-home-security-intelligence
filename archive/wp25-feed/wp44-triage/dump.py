import json, re, collections

SRC='/agents/agent-nemo2/workspace/mutants/backend/services/prompts.py'
lines=open(SRC).read().split('\n')
def_re=re.compile(r'^def (x(.+?))__mutmut_(orig|\d+)\(')
starts=[]
for i,l in enumerate(lines):
    m=def_re.match(l)
    if m: starts.append((i,m.group(1),m.group(3)))
blocks={}
for j,(i,fn,mid) in enumerate(starts):
    end=starts[j+1][0] if j+1<len(starts) else len(lines)
    e=end
    while e>i+1:
        s=lines[e-1].strip()
        if s=='' or s.startswith('mutants_'): e-=1
        else: break
    blocks[(fn,mid)]=(i,e)
def src_of(fn,mid):
    s,e=blocks[(fn,mid)]
    return lines[s+1:e]   # block lines (no def line)

recs=json.load(open('/tmp/wp25/wp44-triage/enriched.json'))
byf=collections.defaultdict(list)
for r in recs: byf[r['fn']].append(r)

out=[]
def word_expand(src,p,n):
    W=re.compile(r'[A-Za-z0-9_.]')
    a=p
    while a>0 and W.match(src[a-1]): a-=1
    b=p+n
    while b<len(src) and W.match(src[b]): b+=1
    return a,b

for fn in sorted(byf, key=lambda f:-len(byf[f])):
    ob=src_of(fn,'orig')
    out.append(f"\n===== {fn}  ({len(byf[fn])} survivors) =====")
    for r in sorted(byf[fn], key=lambda x:x['num']):
        mb=src_of(fn,str(r['num']))
        # find changed lines by line index alignment (blocks are same length usually)
        changed=[]
        if len(ob)==len(mb):
            for li,(a,b) in enumerate(zip(ob,mb)):
                if a!=b:
                    # char-level within line
                    n=min(len(a),len(b)); p=0
                    while p<n and a[p]==b[p]: p+=1
                    q=0
                    while q<(n-p) and a[len(a)-1-q]==b[len(b)-1-q]: q+=1
                    # expand on a
                    a0,a1=word_expand(a,p,len(a)-p-q)
                    # corresponding window in b
                    bp=p-(a0-p*0)  # approx: use same prefix offset
                    bp=p
                    # expand b
                    b1=bp+(len(b)-bp-q)
                    W=re.compile(r'[A-Za-z0-9_.]')
                    while b1<len(b) and W.match(b[b1]): b1+=1
                    changed.append((li+1,a.strip()[:150],b.strip()[:150],a[a0:a1],b[bp:b1]))
        else:
            changed=[(-1,'LEN DIFF', str(len(ob))+' vs '+str(len(mb)), r['del'][:60], r['ins'][:60])]
        for li,a,b,da,db in changed[:2]:
            out.append(f"  {r['num']:>3} L{li}: [-{da!r} +{db!r}]  |{a[:100]}| -> |{b[:100]}|")
open('/tmp/wp25/wp44-triage/dump.txt','w').write('\n'.join(out))
print(len(out))
