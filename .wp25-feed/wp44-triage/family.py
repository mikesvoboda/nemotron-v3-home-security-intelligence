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
    return '\n'.join(lines[s:e])

WORD=re.compile(r'[A-Za-z0-9_]')
recs=json.load(open('/tmp/wp25/wp44-triage/enriched.json'))
for r in recs:
    src=src_of(r['fn'],'orig')
    p=r['p']; d=r['del']; i=r['ins']
    # expand at mutation point to token/word boundaries in BOTH texts
    # left expand: while char before p in original is word char and (for insert) same char aligns
    l0=p
    while l0>0 and WORD.match(src[l0-1]): l0-=1
    # also allow matching ins's left expansion: check mutated src
    msrc=src[:p]+i+src[p+len(d):]
    # right expand
    r0=p+len(d)
    while r0<len(src) and WORD.match(src[r0]): r0+=1
    # canonical del = src[l0:r0] intersected with word span around p..p+len(d)
    wd=src[l0:r0]
    wi=msrc[l0:l0+(r0-l0)-len(d)+len(i)] if False else None
    # simpler: canonical insert = msrc[l0:r0-len(d)+len(i)]
    wi=msrc[l0:(r0-len(d)+len(i))]
    r['cdel']=wd.strip() if wd else ''
    r['cins']=wi.strip() if wi else ''
    # keep raw too

# sanity: cdel/cins should reproduce the diff
def canon_family(r):
    d,i=r['cdel'],r['cins']
    tt=r['toktype']
    instr = tt in ('STRING','FSTRING_MIDDLE','FSTRING_START')
    if d==i: return 'noop?'
    if d=='' :
        if i==') or True': return 'GUARD-OR-True'
        if i==') and False': return 'GUARD-AND-False'
        if i=='not ': return 'INSERT-not'
        if i.startswith('XX'): return 'STR-insertXX' if instr else 'insert:'+i[:12]
        if i=='=': return 'insert-= ??'
        return 'INSERT:'+repr(i)[:20]
    if i=='':
        if d in ('None','0.0','""','{}','[]','False','0','1'): return 'REMOVE-default:'+d
        if d=='not ': return 'REMOVE-not'
        if d in ('and','or','not','in','is'): return 'REMOVE-boolop:'+d
        if d.startswith('XX'): return 'STR-removeXX' if instr else 'rm:'+repr(d)[:14]
        if d in ('enrichment_result','violence_result','clothing','confidence','segment','group_idx','person','seg','reid'): return 'ARG->nothing'
        if instr: return 'STR-remove-text'
        return 'REMOVE:'+repr(d)[:20]
    # replacement
    if d in ('and','or') and i in ('and','or'): return 'BOOLOP-flip'
    if d=='True' and i=='False' or d=='False' and i=='True': return 'BOOL-flip'
    if d=='False' and i=='None' or d=='True' and i=='None' or d=='None' and i in ('True','False'): return 'BOOL<->None'
    if d in ('==','!=','>=','<=','>','<') or i in ('==','!=','>=','<=','>','<'): return 'CMP-flip:'+d+'->'+i
    if d in ('+','-','*','/','%') or i in ('+','-','*','/','%'): return 'ARITH-flip:'+d+'->'+i
    if d=='+' and i=='' : return 'REMOVE-plus'
    if d=='continue' and i=='break' or d=='break' and i=='continue': return 'FLOW-continue<->break'
    # numeric
    try:
        float(d); float(i); return 'NUM-tweak'
    except Exception: pass
    # string content
    if d.upper()==i and d!=i: return 'STR-upper'
    if d.lower()==i and d!=i: return 'STR-lower'
    if d[0].isupper() and i[0].islower() and d[1:].lower()==i[1:].lower(): return 'STR-lower'
    if i.startswith('XX') and i.endswith('XX') and ('XX'+d+'XX')==i: return 'STR-clobber-XX'
    if d.startswith('XX') and ('XX'+i+'XX')==d: return 'STR-unclobber'
    if instr: return 'STR-other:'+repr(d)[:12]+'->'+repr(i)[:12]
    if re.match(r'^[A-Za-z_][A-Za-z0-9_.\[\]\'"]*$',d) and re.match(r'^[A-Za-z_][A-Za-z0-9_.\[\]\'"]*$',i):
        return 'NAME-replace:'+d[:16]+'->'+i[:16]
    return 'OTHER:'+repr(d)[:14]+'->'+repr(i)[:14]

for r in recs: r['family']=canon_family(r)

cnt=collections.Counter(r['family'] for r in recs)
print(len(recs))
for f,c in cnt.most_common(80):
    print(f'{c:4d}  {f}')
json.dump(recs,open('/tmp/wp25/wp44-triage/family.json','w'))
