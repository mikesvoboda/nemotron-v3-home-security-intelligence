import json, re, collections, difflib
SRC='mutants/backend/services/unique_counter_service.py'
META='mutants/backend/services/unique_counter_service.py.meta'
lines=open(SRC).read().splitlines(True)
DEF=re.compile(r'^(\s*)(?:async\s+)?def\s+(\w+)\s*\(')
starts=[(i,m.group(2),len(m.group(1))) for i,l in enumerate(lines) if (m:=DEF.match(l))]
blocks={}
for idx,(i,name,ind) in enumerate(starts):
    end=len(lines)
    for j in range(i+1,len(lines)):
        l=lines[j]
        if l.strip()=='': continue
        cur=len(l)-len(l.lstrip()); mm=DEF.match(l)
        if mm and len(mm.group(1))<=ind: end=j; break
        if cur<=ind and re.match(r'\s*(class\s|@|mutants_)',l): end=j; break
    jj=end
    while jj>i+1 and lines[jj-1].strip()=='': jj-=1
    blocks.setdefault(name, lines[i:jj])
ebk=json.load(open(META))['exit_code_by_key']
surv=sorted([k for k,v in ebk.items() if v==0])
def diffparts(key):
    base=key.rsplit('__mutmut_',1)[0]; orig=base+'__mutmut_orig'
    a=[l.strip() for l in blocks[orig] if l.strip() and not l.strip().startswith('mutants_')]
    b=[l.strip() for l in blocks[key] if l.strip() and not l.strip().startswith('mutants_')]
    a=[x.replace(orig,'#N#') for x in a]; b=[x.replace(key,'#N#') for x in b]
    out=[]
    for tag,i1,i2,j1,j2 in difflib.SequenceMatcher(None,a,b).get_opcodes():
        if tag=='equal': continue
        out.append((' | '.join(a[i1:i2]), ' | '.join(b[j1:j2])))
    return out

def args(s, fname):
    m=re.search(re.escape(fname)+r'\((.*)\)$', s)
    return m.group(1) if m else None

def cluster(fn, parts):
    o=' ~~ '.join(p[0] for p in parts); n=' ~~ '.join(p[1] for p in parts)
    if fn=='x__get_window_start':
        if 'datetime.now' in o+n: return 'A1 tz-arg'
        if re.search(r'\bwindow\s*[!=]=', o+n): return 'B1 window-compare'
        m=re.search(r'replace\((.*)\)\.isoformat', n)
        on=re.search(r'replace\((.*)\)\.isoformat', o)
        oka=dict(re.findall(r'(\w+)=(\d+)', on.group(1))) if on else {}
        nka=dict(re.findall(r'(\w+)=(\d+)', m.group(1))) if m else {}
        if any(int(v)!=0 for v in nka.values()): return 'C1 window-start nonzero'
        if set(nka)<set(oka): return 'D1 dropped trunc kwarg'
        return 'E1 other'
    if fn=='get_cardinality_stats':
        if 'window_start=' in n: return 'F1 window_start'
        if 'get_unique_' in n: return 'G1 window arg dropped'
        return 'E1 other'
    if fn=='get_merged_count': return 'H1 merged-count key/arg'
    m=re.search(r'return await self\._redis\.pfcount', n)
    if m: return 'I1 pfcount(None)'
    na_old=args(o,'pfadd_with_expire'); na_new=args(n.split(' ~~ ')[0],'pfadd_with_expire')
    if na_old is not None and na_new is not None:
        old_is_key_none = na_new.startswith('None,') or (not na_new.startswith('key,'))
        if old_is_key_none: return 'J1 pfadd key arg'
        # compare token lists positionally
        ot=na_old.split(', '); nt=na_new.split(', ')
        if len(nt)==len(ot):
            diffpos=[i for i,(x,y) in enumerate(zip(ot,nt)) if x!=y]
            if diffpos==[1]: return 'K1 pfadd ttl arg'
            return 'L1 pfadd value arg'
        # arg removed
        if 'ttl' in ot[1] and len(nt)==2: return 'L1 pfadd value arg'   # value dropped
        if len(nt)==2 and 'ttl' not in nt[1]: return 'K1 pfadd ttl arg'  # ttl dropped -> (key, value)
        return 'L1 pfadd value arg'
    if 'key = None' in n: return 'M1 key=None'
    na=args(n.split(' ~~ ')[0],'_build_key')
    if na is not None:
        if na=='window': return 'N1 metric arg dropped'
        if na.startswith('None'): return 'N1 metric arg = None'
        if na.endswith(', None'): return 'O1 window arg = None'
        if re.match(r'^"[A-Za-z_]*", \)$', na): return 'P1 window arg dropped (equiv)'
        mv=na.split(', ')[0]
        if mv.upper()==mv.strip('"').upper() and mv.strip('"').lower() in ('cameras','events','detections','entities','detection_types'): return 'Q1 metric case/prefix'
        if mv.startswith('"XX'): return 'Q1 metric case/prefix'
        return 'E1 other'
    return 'E1 other'

cl=collections.defaultdict(list)
for k in surv:
    key=k.split('.')[-1]
    fn=key.rsplit('__mutmut_',1)[0].split('ǁ')[-1]
    parts=diffparts(key)
    cl[cluster(fn,parts)].append((k,' ~ '.join('%s => %s'%p for p in parts)))
tot=0
for c,items in sorted(cl.items()):
    tot+=len(items)
    fns=sorted(set(i[0].split('.')[-1].rsplit('__mutmut_',1)[0].split('ǁ')[-1] for i in items))
    print('%-32s n=%-3d %s'%(c,len(items),','.join(fns)))
    print('    ', items[0][1][:180])
print('TOTAL',tot)
json.dump({c:[i[0] for i in v] for c,v in cl.items()}, open('/tmp/wp25/wp44-triage/clusters_final.json','w'), indent=1)
