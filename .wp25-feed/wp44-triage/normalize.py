import json, re, collections, difflib

raw = json.load(open('/tmp/wp25/wp44-triage/raw_diffs.json'))

def strip_def(hunks):
    # drop hunks that are only the def line (function rename)
    keep = []
    for tag, ol, ml in hunks:
        if ol.startswith('def ') or ml.startswith('def '):
            # keep only if there is other content besides the def line
            o_rest = [l for l in ol.split('\n') if not l.startswith('def ')]
            m_rest = [l for l in ml.split('\n') if not l.startswith('def ')]
            if not o_rest and not m_rest:
                continue
            ol='\n'.join(o_rest); ml='\n'.join(m_rest)
        keep.append((tag, ol.strip('\n'), ml.strip('\n')))
    return keep

def charlevel(a, b):
    """return list of (orig_fragment, mut_fragment) inline differences"""
    sm = difflib.SequenceMatcher(None, a, b)
    frs=[]
    for tag,i1,i2,j1,j2 in sm.get_opcodes():
        if tag=='equal': continue
        frs.append((a[i1:i2], b[j1:j2]))
    return frs

recs=[]
for o in raw:
    h = strip_def(o['hunks'])
    frags=[]
    origline=[]; mutline=[]
    for tag, ol, ml in h:
        if ol==ml: continue
        origline.append(ol); mutline.append(ml)
        frags.extend(charlevel(ol, ml))
    # collapse a lone 'op' style: if single fragment pair
    recs.append({'fn':o['fn'],'num':o['num'],'key':o['key'],
                 'orig':'\n'.join(origline),'mut':'\n'.join(mutline),
                 'frags':frags})

json.dump(recs, open('/tmp/wp25/wp44-triage/norm_diffs.json','w'))

# Fragment-level pattern census across all survivors
def fkind(of, mf):
    of_s, mf_s = of.strip(), mf.strip()
    ops = {'==','!=','>=','<=','>','<',' and ',' or ',' is not ',' in ',' not in ','is '}
    if of_s and not mf_s: return f'delete:{of_s!r}'
    if mf_s and not of_s: return f'insert:{mf_s!r}'
    if of_s in ops or mf_s in ops: return f'op:{of_s}->{mf_s}'
    # numeric
    try:
        float(of_s); float(mf_s); return 'number'
    except Exception: pass
    if of_s.startswith('"') or of_s.startswith("'") or mf_s.startswith('"') or mf_s.startswith("'"):
        return 'string'
    if of_s in ('True','False') or mf_s in ('True','False'): return 'bool'
    if of_s.startswith('_') or re.match(r'^[A-Za-z_][\w.]*$', of_s) and re.match(r'^[A-Za-z_][\w.]*$', mf_s):
        return 'name'
    return 'other'

cnt = collections.Counter()
for r in recs:
    ks = tuple(sorted(fkind(a,b) for a,b in r['frags']))
    cnt[(r['fn'], ks)] += 1
print('distinct (fn, fragment-pattern) groups:', len(cnt))
tot=0
for (fn,ks),c in sorted(cnt.items(), key=lambda kv:-kv[1]):
    tot+=c
print('total', tot)
# kinds census
k2=collections.Counter()
for r in recs:
    for a,b in r['frags']:
        k2[fkind(a,b)]+=1
for k,v in k2.most_common(40): print(v, k)
