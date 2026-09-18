import json, re, difflib, collections
exec(open('/tmp/wp25/wp44-triage/final.py').read().split("clusters=json.load")[0])  # reuse blocks/delta

clusters=json.load(open('/tmp/wp25/wp44-triage/clusters_struct.json'))
agg=json.load(open('/tmp/wp25/wp44-triage/final_clusters.json'))

# per-mutant refinement of TB-CORE and CLOSE-STATE
TB_RULES=[
 ('OPFLIP', lambda a,b: ('>= self._batch_window' in a or '>= self._idle_timeout' in a) and '>' in b and '>=' not in b),
 ('IDX',    lambda a,b: 'metadata_results[' in a),
 ('NEG',    lambda a,b: re.search(r'- ',a) and '+ ' in b),
 ('DEAD',   lambda a,b: 'should_close = True' in a or ('should_close = False' in a and 'True' in b)),
]
def tb_class(k):
    for a,b in delta(k):
        for name,f in TB_RULES:
            if f(a,b): return name
    return 'WIRE'
def close_class(k):
    frs=delta(k)
    j=' '.join(a+' '+b for a,b in frs)
    if 'queue_item' in ' '.join(a for a,b in frs): return 'QUEUEITEM'
    if 'float(started_at_str)' in j and ('and False' in j or 'or True' in j): return 'FALLBACK'
    if 'already_closed' in j or 'detections": []' in j or 'return {' in j: return 'ALREADY-DICT'
    return 'STATE'

new=collections.defaultdict(list)
for k in agg['TB-CORE']: new['TB-'+tb_class(k)].append(k)
for k in agg['CLOSE-STATE']: new['CLOSE-'+close_class(k)].append(k)
# broadcaster wiring -> merge into PAYLOAD
for k in agg[[k2 for k2 in agg if k2.startswith('OTHER:_broadcast_detection_batch|CODE')][0]]: agg['PAYLOAD'].append(k)
for k in agg[[k2 for k2 in agg if k2.startswith('OTHER:_broadcast_detection_new|CODE')][0]]: agg['PAYLOAD'].append(k)
del agg[[k2 for k2 in agg if k2.startswith('OTHER:_broadcast')][0]] if len([k2 for k2 in agg if k2.startswith('OTHER:_broadcast')])==1 else None
# fix: remove both
for k2 in [k2 for k2 in list(agg) if k2.startswith('OTHER:_broadcast')]: del agg[k2]
agg.update(new)
# smoke/fire MIX exc_info -> LOGEXTRA
agg['LOGEXTRA'].append(agg.pop('OTHER:_process_smoke_fire_fast_path|MULTI-REAL:[\'CODE:\', \'LOG\']|MIX|exc_info')[0])
# LRANGE-ARGS: lrange args invisible through mock → EQUIVALENT
# MISC-EQUIV, LOCKWIRE → EQUIVALENT
json.dump({k:v for k,v in agg.items()}, open('/tmp/wp25/wp44-triage/final_clusters.json','w'))
tot=0
for cls,ks in sorted(agg.items(),key=lambda x:-len(x[1])):
    tot+=len(ks); print(f'{len(ks):4d} {cls:14s} ex={ks[:2]}')
print('TOTAL',tot)
