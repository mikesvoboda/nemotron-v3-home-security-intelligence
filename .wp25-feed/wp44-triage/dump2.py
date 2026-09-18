import json, re, collections

SRC='/agents/agent-nemo2/workspace/mutants/backend/services/prompts.py'
ORIG='/agents/agent-nemo2/workspace/backend/services/prompts.py'
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
def block(fn,mid):
    s,e=blocks[(fn,mid)]
    return lines[s:e]   # includes def line

# original source lines for locating
olines=open(ORIG).read().split('\n')

def within_line_diff(a,b):
    n=min(len(a),len(b)); p=0
    while p<n and a[p]==b[p]: p+=1
    q=0
    while q<(n-p) and a[len(a)-1-q]==b[len(b)-1-q]: q+=1
    return a[p:len(a)-q], b[p:len(b)-q]

W=re.compile(r'[A-Za-z0-9_.]')
def word_expand(s,i):
    a=i
    while a>0 and W.match(s[a-1]): a-=1
    return a

surv=[l.strip() for l in open('/tmp/wp25/wp44-triage/survivor_keys.txt') if l.strip()]
byf=collections.defaultdict(list)
for k in surv:
    m=re.match(r'^backend\.services\.prompts\.(x.+?)__mutmut_(\d+)$',k)
    byf[m.group(1)].append((int(m.group(2)),k))

out=[]
recs=[]
multi=0
for fn in sorted(byf, key=lambda f:-len(byf[f])):
    ob=block(fn,'orig')
    # skip def line: body starts after def (find first line after 'def')
    body0=1
    out.append(f"\n===== {fn}  ({len(byf[fn])} survivors) =====")
    for num,k in sorted(byf[fn]):
        mb=block(fn,str(num))
        L=min(len(ob),len(mb))
        diffs=[]
        for li in range(body0,L):
            if ob[li]!=mb[li]:
                diffs.append(li)
        if len(diffs)!=1:
            multi+=1
            out.append(f"  #{num}: MULTI/NONE-line diff lines={diffs}  (len {len(ob)}/{len(mb)})")
            for li in diffs[:4]:
                a=ob[li] if li<len(ob) else '?'
                b=mb[li] if li<len(mb) else '?'
                d,i=within_line_diff(a,b)
                out.append(f"      L{li+1}: [-{d!r}+{i!r}] |{a.strip()[:120]}| -> |{b.strip()[:120]}|")
            continue
        li=diffs[0]
        a=ob[li]; b=mb[li]
        d,i=within_line_diff(a,b)
        # locate line in original source
        src_line=a.strip()
        loc=[n+1 for n,l in enumerate(olines) if l.strip()==src_line]
        recs.append({'fn':fn,'num':num,'key':k,'body_line':li+1,'orig_line':a.strip(),
                     'mut_line':b.strip(),'del':d,'ins':i,'orig_src_lines':loc[:5]})
        out.append(f"  #{num:>3} L{li+1} src~{loc[0] if loc else '?'}: [-{d!r} +{i!r}]  |{a.strip()[:110]}|")
open('/tmp/wp25/wp44-triage/dump2.txt','w').write('\n'.join(out))
json.dump(recs,open('/tmp/wp25/wp44-triage/line_diffs.json','w'))
print('single-line recs',len(recs),'multi',multi)
