import json, collections
# reuse classifier
exec(open('/tmp/wp25/wp44-triage/cd_classify.py').read().split("out=collections.Counter()")[0])

path='/agents/agent-nemo2/workspace/mutants/backend/services/container_discovery.py'
meta=json.load(open(path+'.meta'))
ebd=meta['exit_code_by_key']

# need startup_grace/max_failures removal equivalence split: value of the removed kwarg in orig
# recompute per-mutant with removed-line value
def diff_lines(fn):
    base,num=fn.rsplit('__mutmut_',1)
    a=funcs[base+'__mutmut_orig'].splitlines()
    b=funcs[fn].splitlines()
    a[0]=a[0].replace('__mutmut_orig',''); b[0]=b[0].replace('__mutmut_'+num,'')
    return [l for l in difflib.unified_diff(a,b,lineterm='',n=0) if l[:1] in '+-' and l[:3] not in ('---','+++')]

def cluster_of(k):
    fn=k.split('.')[-1]
    fnm=fn.rsplit('__mutmut_',1)[0].replace('xǁContainerDiscoveryServiceǁ','CDService.').replace('x_','')
    tgt,kind=classify(fn)
    d=diff_lines(fn)
    rm=[l[1:].strip() for l in d if l[0]=='-' and l[1:].strip() not in NOISE]
    ad=[l[1:].strip() for l in d if l[0]=='+' and l[1:].strip() not in NOISE]
    old=rm[0] if rm else ''
    if fnm=='build_service_configs':
        if tgt.startswith('ternary:'): return 'B1 port settings/default ternary (None/forced/plus1)'
        if tgt=='port' and kind=='to_None': return 'B2 port= -> None'
        if tgt=='dict-key': return 'B3 dict key case/XXwrap'
        if tgt=='display_name': return 'B4 display_name case/XXwrap/None'
        if tgt=='category': return 'B5 category -> None'
        if tgt=='health_endpoint' and kind in ('case','XXwrap') or (tgt=='health_endpoint' and kind.startswith('other')): return 'B6 health_endpoint value case/XXwrap'
        if tgt=='health_endpoint': return 'B7 health_endpoint -> None/removed'
        if tgt=='health_cmd': return 'B8 health_cmd case/XX/None/removed'
        if tgt=='max_failures' and kind=='to_None': return 'B10 max_failures -> None'
        if tgt=='max_failures' and kind=='plus1': return 'B11 max_failures +1'
        if tgt=='max_failures' and kind=='removed':
            val=old.split('=')[1].strip().rstrip(',')
            return 'B12a max_failures dropped, INFRA (10->5)' if val=='10' else 'B12b max_failures dropped, MON (5->5 EQUIV)'
        if tgt=='restart_backoff_base': return 'B13 restart_backoff_base None/plus1/removed'
        if tgt=='restart_backoff_max': return 'B14 restart_backoff_max None/plus1/removed'
        if tgt=='startup_grace_period' and kind in ('to_None','plus1'): return 'B15 startup_grace_period None/+1'
        if tgt=='startup_grace_period' and kind=='removed':
            val=old.split('=')[1].strip().rstrip(',')
            return 'B16a startup_grace dropped, value already 60 (EQUIV)' if val=='60' else 'B16b startup_grace dropped, default 60 wins'
    elif fnm=='CDService._create_managed_service':
        if kind=='other' and ('image' in old or 'tags' in old or old.startswith('image =')):
            num=fn.rsplit('__mutmut_',1)[1]
            if num in ('6','13','16'): return 'D1 untagged/image getattr EQUIV defaults'
            if num=='28': return 'D2 untagged-image f-string getattr/slice (incl 28 argdrop)'
            return 'D2 untagged-image f-string getattr/slice (incl 28 argdrop)'
        if tgt=='container_id': return 'D3 container_id getattr default LOW-VALUE'
        if tgt=='health_cmd': return 'D4 health_cmd passthrough -> None/removed'
        return 'D? other '+tgt
    elif fnm=='CDService.discover_all':
        return 'E1 discover_all log message/extra dict mutations'
    elif fnm=='CDService.match_container_name':
        return 'F1 match_container_name sort key=len dropped (tie order)'
    elif fnm=='build_configs_from_compose':
        num=fn.rsplit('__mutmut_',1)[1]
        if num=='4': return 'G1 build_configs_from_compose logger.warning(None) EQUIV'
        return 'G2 build_configs_from_compose parse/fallback mutations'
    return 'ZZ unmatched '+fnm+' '+tgt+' '+kind

cl=collections.defaultdict(list)
for k,v in ebd.items():
    if v==0: cl[cluster_of(k)].append(k)

tot=0
for name in sorted(cl):
    ks=sorted(cl[name], key=lambda x:int(x.rsplit('__mutmut_',1)[1]))
    tot+=len(ks)
    ex=', '.join(ks[:3])
    print(f"{name}: n={len(ks)}  ex: {ex}")
print('TOTAL',tot)
json.dump({n:ks for n,ks in cl.items()}, open('/tmp/wp25/wp44-triage/cd_final_clusters.json','w'), indent=1)
