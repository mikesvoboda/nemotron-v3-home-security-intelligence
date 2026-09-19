import json, re, collections

meta = json.load(open('/agents/agent-nemo2/workspace/mutants/backend/services/container_discovery.py.meta'))
ebk = meta['exit_code_by_key']
surv = set(k for k,v in ebk.items() if v==0)
def k2bn(k):
    base, num = k.rsplit('__mutmut_',1)
    return (base[len('backend.services.container_discovery.x'):], int(num))
bn_surv = set(k2bn(k) for k in surv)

diffs = json.load(open('/tmp/wp25/wp44-triage/diffs.json'))
dbn = {}
for k,c in diffs.items():
    b,n = k.rsplit('__mutmut_',1)
    dbn[(b,int(n))] = c

residual = [('x_build_configs_from_compose',n) for n in (4,6,8)]
residual += [('x_build_service_configs',n) for n in (249,284,302,360,387,414,441,468,495,521,522,549,575,602,629,656,683,710)]
residual += [('xǁContainerDiscoveryServiceǁ__init__',n) for n in (5,8,9)]
residual += [('xǁContainerDiscoveryServiceǁ_create_managed_service',n) for n in (6,13,16,25,28,31,32,60,63,66)]
residual += [('xǁContainerDiscoveryServiceǁdiscover_all',n) for n in (18,19,21,22,23,24,25,26,27,28,29,30,31,33,34,35)]
residual += [('xǁContainerDiscoveryServiceǁmatch_container_name',n) for n in (5,7)]
bn_res = set((b[1:],n) for b,n in residual)
assert bn_res <= bn_surv

def substantive(bn):
    c = dbn[bn]
    real = [(o,n) for o,n in c if 'mutants_' not in n]
    o,n = real[0]
    po = [p.strip() for p in o.split(' | ')]
    po = [p for p in po if re.match(r'^[\w"\x27]', p)]
    pn = [p.strip() for p in n.split(' | ')]
    pn = [p for p in pn if re.match(r'^[\w"\x27]', p) or p=='' ]
    newp = pn[0] if pn else n
    # a deleted kwarg: new side is only a paren/empty
    raw_new = real[0][1]
    if re.fullmatch(r'\s*\)?\s*(\|\s*\))?|', raw_new.replace(' | ','')) or raw_new.strip() in ('',')',') ,','),'):
        newp = ''
    return (po[0] if po else o.strip(), newp)

rows = collections.defaultdict(list)
for bn in bn_surv:
    base = bn[0]
    old,new = substantive(bn)
    m = re.match(r'^"?([\w-]+)"?: ServiceConfig\($', old)
    if base == 'x_build_service_configs' or base=='_build_service_configs':
        if m: rows['BSD-A dict key UPPER/XXwrap'].append(bn); continue
        if ' if settings else ' in old:
            if new.endswith('= None'): rows['BSD-B port-ternary LHS=None (crash settings=None)').append(bn)
            elif 'and False' in new: rows['BSD-C ternary cond and-False (settings ignored -> defaults)').append(bn)
            elif 'or True' in new: rows['BSD-D ternary cond or-True (AttributeError settings=None)').append(bn)
            else: rows['BSD-E ternary else-default +1 (bad .env-less port)').append(bn)
            continue
        f = (re.match(r'^(\w+)=', old) or [None,'?'])[1] if re.match(r'^(\w+)=', old) else '?'
        deleted = (new == '')
        if f=='display_name': rows['BSD-F display_name UPPER/lower/XX/None').replace(')','')].append(bn)
        elif f=='health_endpoint': rows['BSD-G health_endpoint UPPER/XX/None/deleted'].append(bn)
        elif f=='health_cmd': rows['BSD-H health_cmd case/XX/None/deleted'].append(bn)
        elif f=='port': rows['BSD-B2 port=var -> None').replace(')','')].append(bn) if False else rows['BSD-B2 port=var -> None'].append(bn)
        elif f=='category': rows['BSD-I category -> None (crash/None category)').append(bn)
        elif f=='startup_grace_period':
            v = re.search(r'=(\d+)', old).group(1)
            if deleted and v=='60': rows['BSD-J startup_grace=60 kwarg deleted (== default 60)').replace(')','')].append(bn)
            elif deleted: rows['BSD-K startup_grace kwarg deleted !=60 (default 60 wins)').replace(')','')].append(bn)
            else: rows['BSD-L startup_grace value +1 / None').replace(')','')].append(bn)
        elif f=='max_failures':
            v = re.search(r'=(\d+)', old).group(1)
            if deleted and v=='5': rows['BSD-M max_failures=5 kwarg deleted (== default 5)').replace(')','')].append(bn)
            elif deleted: rows['BSD-N max_failures=10 kwarg deleted (default 5 wins)').replace(')','')].append(bn)
            else: rows['BSD-O max_failures value +1 / None').replace(')','')].append(bn)
        elif f=='restart_backoff_base':
            rows['BSD-P backoff_base kwarg deleted (default 5.0 wins)').replace(')','')].append(bn) if deleted else rows['BSD-Q backoff_base value +1 / None').replace(')','')].append(bn)
        elif f=='restart_backoff_max':
            rows['BSD-R backoff_max kwarg deleted (default 300.0 wins)').replace(')','')].append(bn) if deleted else rows['BSD-S backoff_max value +1 / None').replace(')','')].append(bn)
        else: rows['BSD-Z '+old[:40]].append(bn)
    elif base=='_build_configs_from_compose':
        if old.startswith('logger.warning'): rows['C1 warning message -> None').replace(')','')].append(bn)
        elif 'build_service_configs(' in old:
            if re.search(r'[, ](None|\))\s*$', new) or new.endswith('None)') or new.endswith('settings, ') or 'None' in new.split('(',1)[-1]: rows['C2 fallback flag -> None/dropped (int flag unchanged)').replace(')','')].append(bn)
            else: rows['C3 arg swallow -> immediate crash').replace(')','')].append(bn)
        else: rows['C3 arg swallow -> immediate crash').replace(')','')].append(bn)
    elif base.endswith('__init__'):
        if 'if settings else' in old: rows['I1 include_monitoring else-branch True->False').replace(')','')].append(bn)
        else: rows['I2 build_configs_from_compose call: settings->None or flag->None').replace(')','')].append(bn)
    elif 'discover_all' in base: rows['D1 logging-only (message text / extra dict)').replace(')','')].append(bn)
    elif 'match_container_name' in base: rows['S1 sort key=len dropped').replace(')','')].append(bn)
    elif '_create_managed_service' in base:
        if old.startswith('health_cmd='): rows['M0 health_cmd -> None / kwarg dropped').replace(')','')].append(bn)
        elif 'untagged' in old:
            if '[:13]' in new: rows['M1b untagged slice 12->13').replace(')','')].append(bn)
            elif new=='' or 'getattr(container, ' not in new.replace("getattr(None,","x"): rows['M1a untagged getattr(container,id) default tweaks').append(bn)
            else: rows['M1a untagged getattr(container,id) default tweaks').append(bn)
        elif 'getattr(image_tags' in old:
            if new=='': rows['M2b tags default dropped (TypeError on .tags=None)').replace(')','')].append(bn)
            else: rows['M2a tags default []->None (both falsy)').replace(')','')].append(bn)
        elif 'getattr(container, "image"' in old: rows['M3 image default dropped (TypeError None not None)').replace(')','')].append(bn)
        elif old.startswith('container_id='): rows['M4 container_id getattr default tweaks').replace(')','')].append(bn)
        else: rows['M9 '+old[:40]].append(bn)
    else: rows['ZZ '+base].append(bn)

total=0
for r, keys in sorted(rows.items()):
    inres=[k for k in keys if k in bn_res]
    ks=['x'+b+f'__mutmut_{n}' for b,n in sorted(keys)]
    total+=len(keys)
    print(f'{len(keys):4d} res={len(inres):2d}  {r:62s} {ks[:3]}')
print('SUM', total, total==696)
