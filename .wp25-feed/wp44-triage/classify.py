import json, re, collections

recs=json.load(open('/tmp/wp25/wp44-triage/line_diffs.json'))
enr={ (r['fn'],r['num']):r for r in json.load(open('/tmp/wp25/wp44-triage/enriched.json')) }

def in_str(l, i):
    """is char index i inside a string literal in line l? (naive but robust enough)"""
    q=None; esc=False
    n=0
    while n<len(l):
        c=l[n]
        if q:
            if esc: esc=False
            elif c=='\\': esc=True
            elif c==q: q=None
        else:
            if c in '"\'': q=c
        if n==i: return q is not None
        n+=1
    return False

def shape(d,i,l):
    """classify the mutation shape"""
    if i==') or True' or (i.endswith(') or True')): return 'or-True'
    if i.endswith(') and False'): return 'and-False'
    if d=='or' and i=='and': return 'boolop-or->and'
    if d=='and' and i=='or': return 'boolop-and->or'
    if d=='not ' and i=='': return 'drop-not'
    if i=='not ': return 'insert-not'
    if i=='!' : return 'insert-not'
    if d in ('True','False') and i in ('True','False') and d!=i: return 'bool-flip'
    if d in ('==','!=','<','<=','>','>=','in','is','is not','not in'):
        if i in ('==','!=','<','<=','>','>=','in','is','is not','not in'): return 'cmp-flip'
    if d=='continue' and i=='break': return 'continue->break'
    if d=='break' and i=='continue': return 'break->continue'
    try:
        fd=float(d); fi=float(i)
        if fd==fi: return 'num-rewrite'
        return 'num-tweak'
    except Exception: pass
    if d==i.lower() or d.upper()==i: return 'str-case'
    if i.startswith('XX') and i.endswith('XX') and i[2:-2]==d: return 'str-XXwrap'
    if d=='' or i=='': return 'insert-del'
    if re.match(r'^[A-Za-z_][\w.]*$',d) and re.match(r'^[A-Za-z_][\w.]*$',i): return 'name-swap'
    return 'text-swap'

# find char offset of the change in orig line for str detection
census=collections.Counter()
detail=collections.defaultdict(list)
for r in recs:
    l=r['orig_line']; m=r['mut_line']
    d,i=r['del'],r['ins']
    # recompute position in stripped line
    p=l.find(d) if d else 0
    # better: common prefix of l,m
    n=min(len(l),len(m)); q=0
    while q<n and l[q]==m[q]: q+=1
    instr=in_str(l,q)
    r['instr']=instr
    # is line a docstring/prose? heuristic: inside triple quotes -> use enriched toktype
    e=enr.get((r['fn'],r['num']),{})
    r['toktype']=e.get('toktype')
    sh=shape(d,i,l)
    r['shape']=sh
    if r['toktype'] in ('STRING','FSTRING_START') or (instr and sh not in ('or-True','and-False','boolop-or->and','boolop-and->or','drop-not','insert-not','bool-flip','cmp-flip','continue->break','break->continue','num-rewrite')):
        # string-region mutation
        if sh=='str-case': cat='STR-case'
        elif sh=='str-XXwrap': cat='STR-XXclobber'
        elif d in ('unknown','confidence','is_suspicious') or d.startswith('unknown'): cat='STR-key-or-default-text'
        else: cat='STR-other-text'
    elif sh in ('or-True','and-False','boolop-or->and','boolop-and->or','drop-not','insert-not'): cat='LOGIC-'+sh
    elif sh in ('bool-flip','cmp-flip'): cat='LOGIC-'+sh
    elif sh in ('continue->break','break->continue'): cat='LOGIC-flow'
    elif sh=='num-tweak': cat='NUM-tweak'
    elif sh=='num-rewrite': cat='NUM-rewrite'
    else:
        if d in ('None','0','0.0','""','{}','[]','False','True') or i in ('None','0','0.0','""','{}','[]','False','True'): cat='CONST-default-swap'
        elif sh=='name-swap': cat='NAME-swap'
        elif sh=='insert-del': cat='INSERT/DEL-'+(d or i)[:10]
        else: cat='SWAP-other'
    r['cat']=cat
    census[(cat, r['fn'])]+=1
    detail[cat].append(r)

print(collections.Counter(r['cat'] for r in recs).most_common(30))
print('unmatched? total', sum(census.values()))
json.dump(recs,open('/tmp/wp25/wp44-triage/line_diffs.json','w'))
json.dump({k:v for k,v in detail.items()}, open('/tmp/wp25/wp44-triage/buckets.json','w'))
