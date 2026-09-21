import re, difflib, json, sys

MUT='/agents/agent-nemo2/workspace/mutants/backend/services/depth_anything_loader.py'
KEYS='/tmp/wp25/wp44-triage/keys_exact.txt'
PRE='backend.services.depth_anything_loader.'

lines=open(MUT).read().splitlines()
defpat=re.compile(r'^(\s*)(?:async )?def ([A-Za-z0-9ǁ_]+__mutmut_(?:\d+|orig))[\(=]')
starts=[]  # (lineno0, indent, name)
for i,l in enumerate(lines):
    m=defpat.match(l)
    if m:
        starts.append((i,len(m.group(1)),m.group(2)))

# body end: next def start with indent <= this indent
def body(idx):
    i,ind,name=starts[idx]
    # skip past (possibly multi-line) signature until depth 0
    depth=0; j=i
    while j < len(lines):
        depth += lines[j].count('(')-lines[j].count(')')
        depth += lines[j].count('[')-lines[j].count(']')
        if depth<=0 and lines[j].rstrip().endswith(':'):
            break
        j+=1
    end=len(lines)
    for k in range(j+1,len(lines)):
        l=lines[k]
        if not l.strip(): continue
        cur=len(l)-len(l.lstrip())
        if cur<=ind:
            end=k; break
    return '\n'.join(lines[i:end])

byidx={s[2]:k for k,s in enumerate(starts)}
missing=set()

def variant_diff(fnname, num):
    base=fnname+'__mutmut_orig'
    var=fnname+f'__mutmut_{num}'
    if base not in byidx or var not in byidx:
        missing.add(var); return None
    a=body(byidx[base]).splitlines()
    b=body(byidx[var]).splitlines()
    # strip decorator lines
    d=list(difflib.unified_diff(a,b,lineterm='',n=1))
    return [x for x in d if x.startswith(('+','-','@')) and not x.startswith(('+++','---'))]

out={}
for key in open(KEYS).read().split():
    fn=key[len(PRE):]
    m=re.match(r'(.+)__mutmut_(\d+)$',fn)
    if not m: out[key]={'err':'nomatch'}; continue
    fnname,num=m.group(1),int(m.group(2))
    d=variant_diff(fnname,num)
    if d is None:
        out[key]={'err':'missing-variant'}
    else:
        # keep only changed content lines (drop @@ headers for compactness)
        out[key]=[l for l in d if not l.startswith('@@')]

json.dump(out,open('/tmp/wp25/wp44-triage/variant_diffs.json','w'),indent=0)
print('keys',len(out),'missing',len(missing))
if missing: print(sorted(list(missing))[:20])
