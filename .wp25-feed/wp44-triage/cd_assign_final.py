exec(open('/tmp/wp25/wp44-triage/cd_classify.py').read().split("out=collections.Counter()")[0])
import json as _j, collections
meta=_j.load(open('/tmp/wp25/wp44-triage/cd-meta-frozen.json'))

def cluster_of(k):
    fn=k.split('.')[-1]
    fnm=fn.rsplit('__mutmut_',1)[0].replace('xǁContainerDiscoveryServiceǁ','CDService.').replace('x_','')
    tgt,kind=classify(fn)
    d=diff_of(fn)
    rm=[l[1:].strip() for l in d if l[0]=='-' and l[1:].strip() not in NOISE]
    ad=[l[1:].strip() for l in d if l[0]=='+' and l[1:].strip() not in NOISE]
    old=rm[0] if rm else ''
    num=int(fn.rsplit('__mutmut_',1)[1])
    if fnm=='build_service_configs':
        if tgt.startswith('ternary:'): return 'B1'
        if tgt=='port' and kind=='to_None': return 'B2'
        if tgt=='dict-key': return 'B3'
        if tgt=='display_name': return 'B4'
        if tgt=='category': return 'B5'
        if tgt=='health_endpoint' and (kind=='case' or kind=='XXwrap' or kind.startswith('other')): return 'B6'
        if tgt=='health_endpoint': return 'B7'
        if tgt=='health_cmd': return 'B8'
        if tgt=='max_failures' and kind=='to_None': return 'B10'
        if tgt=='max_failures' and kind=='plus1': return 'B11'
        if tgt=='max_failures' and kind=='removed':
            return 'B12a' if old.split('=')[1].strip().rstrip(',')=='10' else 'B12b'
        if tgt=='restart_backoff_base': return 'B13'
        if tgt=='restart_backoff_max': return 'B14'
        if tgt=='startup_grace_period' and kind in ('to_None','plus1'): return 'B15'
        if tgt=='startup_grace_period' and kind=='removed':
            return 'B16a' if old.split('=')[1].strip().rstrip(',')=='60' else 'B16b'
    elif fnm=='CDService._create_managed_service':
        if num in (6,13,16): return 'D1'
        if tgt=='container_id': return 'D3'
        if tgt=='health_cmd': return 'D4'
        return 'D2'
    elif fnm=='CDService.discover_all': return 'E1'
    elif fnm=='CDService.match_container_name': return 'F1'
    elif fnm=='build_configs_from_compose':
        return 'G1' if num==4 else 'G2'
    elif fnm=='CDService.__init__': return 'H1'
    return 'ZZ'

cl=collections.defaultdict(list)
for k,v in meta['exit_code_by_key'].items():
    if v==0: cl[cluster_of(k)].append(k)
out={}
tot=0
for name in sorted(cl):
    ks=sorted(cl[name], key=lambda x:int(x.rsplit('__mutmut_',1)[1]))
    tot+=len(ks)
    out[name]=ks
    print(f"{name}: n={len(ks)}  ex={ks[0].split('.',2)[-1]}")
print('TOTAL',tot)
_j.dump(out, open('/tmp/wp25/wp44-triage/cd_clusters_frozen.json','w'), indent=1)
