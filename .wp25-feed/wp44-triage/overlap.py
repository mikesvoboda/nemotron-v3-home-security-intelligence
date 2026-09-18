import json, collections

recs=json.load(open('/tmp/wp25/wp44-triage/line_diffs.json'))
fa=json.load(open('/tmp/wp25/wp44-triage/fn_asserts.json'))
fa={k:set(v) for k,v in fa.items()}

STR_ROLES={'prose','prompt-text','prompt-output','fstring-literal','default-value','semantic-key','dict-value','semantic-compare','semantic-attr'}
verdict=collections.Counter()
breaks=[]; gaps=[]; nomatch=[]
for r in recs:
    fn=r['fn']; d=r['del']; i=r['ins']; ol=r['orig_line']; ml=r['mut_line']
    asserts=fa.get(fn,set())
    hit=None
    for a in asserts:
        # does assertion literal intersect the mutated character region of the line?
        p=ol.find(d) if d else ol.find(i, 0) if i else 0
        # better: common prefix
        n=min(len(ol),len(ml)); q=0
        while q<n and ol[q]==ml[q]: q+=1
        # region = ol[q:q+len(d)-...]; just use: a present in ol and not in ml → mutation breaks it
        if a and a in ol and a not in ml:
            hit=('breaks',a); break
        if a and a in ml and a not in ol:
            hit=('creates',a); break
    r['assert_hit']=hit
    if hit: breaks.append(r); verdict[('BREAKS-asserted', hit[0])]+=1
    else:
        role=r.get('role')
        if role in STR_ROLES:
            gaps.append(r); verdict[('no-assert-overlap', role)]+=1
        elif role in ('semantic-attr','NO-STR-HIT'):
            verdict[('code-region', role)]+=1
        else:
            verdict[('other',role)]+=1
json.dump(recs, open('/tmp/wp25/wp44-triage/line_diffs.json','w'))
for k,v in verdict.most_common(25): print(f'{v:4d}  {k}')
print('--- BREAKS-asserted (survived despite asserted literal overlap => check anomaly) ---')
for r in breaks[:40]:
    print(r['fn'], '#'+str(r['num']), '|', r['del'][:40],'->',r['ins'][:30], '| assert:', r['assert_hit'][1][:50])
print('count breaks', len(breaks))
