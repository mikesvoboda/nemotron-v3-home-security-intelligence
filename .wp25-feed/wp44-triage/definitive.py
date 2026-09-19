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

residual = [
 ('_build_configs_from_compose',4),('_build_configs_from_compose',6),('_build_configs_from_compose',8),
] + [('_build_service_configs',n) for n in (249,284,302,360,387,414,441,468,495,521,522,549,575,602,629,656,683,710)] \
  + [('ǁContainerDiscoveryServiceǁ__init__',n) for n in (5,8,9)] \
  + [('ǁContainerDiscoveryServiceǁ_create_managed_service',n) for n in (6,13,16,25,28,31,32,60,63,66)] \
  + [('ǁContainerDiscoveryServiceǁdiscover_all',n) for n in (18,19,21,22,23,24,25,26,27,28,29,30,31,33,34,35)] \
  + [('ǁContainerDiscoveryServiceǁmatch_container_name',n) for n in (5,7)]
bn_res = set(residual)
assert bn_res <= bn_surv, sorted(bn_res - bn_surv)

def first_line_change(bn):
    c = dbn[bn]
    real = [(o,n) for o,n in c if 'mutants_' not in n]
    o,n = real[0]
    # normalize spans like "field=X, | )," -> keep field part only
    po = [p for p in o.split(' | ') if re.match(r'^[\w"\x27]', p) or '=' in p]
    pn = [p for p in n.split(' | ') if re.match(r'^[\w"\x27]', p) or '=' in p or p=='']
    return (po[0] if po else o, (pn[0] if pn else n))

rows = collections.defaultdict(list)
for bn in bn_surv:
    base = bn[0]
    old,new = first_line_change(bn)
    if base == '_build_service_configs':
        m = re.match(r'^"?([\w-]+)"?: ServiceConfig\($', old)
        if m: rows['BSD-A dict key string tweak (UPPER/XXwrap)'].append(bn); continue
        if ' if settings else ' in old:
            if new.endswith('= None') or new == old.split('=')[0].strip()+' = None': rows['BSD-B port-ternary LHS -> None'].append(bn)
            elif 'and False' in new: rows['BSD-C ternary cond -> `and False` (settings silently ignored)'].append(bn)
            elif 'or True' in new: rows['BSD-D ternary cond -> `or True` (crash when settings=None)'].append(bn)
            else: rows['BSD-E ternary else-default +1'].append(bn)
            continue
        m = re.match(r'^(\w+)=', old)
        f = m.group(1) if m else None
        newv = new
        deleted = re.sub(r'^\w+=','',old) == newv or newv == '' or newv == ')'
        if f == 'display_name': rows['BSD-F display_name string tweak (UPPER/lower/XX/None)'].append(bn)
        elif f == 'health_endpoint': rows['BSD-G health_endpoint string tweak (UPPER/XX/None/deleted)'].append(bn)
        elif f == 'health_cmd': rows['BSD-H health_cmd string tweak (case/XX/None/deleted)'].append(bn)
        elif f == 'port': rows['BSD-B2 port=var -> None'].append(bn)
        elif f == 'category': rows['BSD-I category=ServiceCategory.X -> None'].append(bn)
        elif f == 'startup_grace_period':
            v = re.match(r'^\w+=(\d+),$', old).group(1)
            if newv == '':
                rows['BSD-J startup_grace_period kwarg deleted (value==default 60)'] if v=='60' else rows['BSD-K startup_grace_period kwarg deleted (value!=default)']
                rows['BSD-J startup_grace_period kwarg deleted (value==default 60)' if v=='60' else 'BSD-K startup_grace_period kwarg deleted (value!=60, default 60 wins)'].append(bn)
            else: rows['BSD-L startup_grace_period value +1 / ->None'].append(bn)
        elif f == 'max_failures':
            v = re.match(r'^\w+=(\d+),$', old).group(1)
            if newv == '':
                rows['BSD-M max_failures=5 kwarg deleted (== default 5)'].append(bn) if v=='5' else rows['BSD-N max_failures=10 kwarg deleted (default 5 wins)'].append(bn)
            else: rows['BSD-O max_failures value +1 / ->None'].append(bn)
        elif f == 'restart_backoff_base':
            if newv in ('',')'): rows['BSD-P restart_backoff_base kwarg deleted (default 5.0 wins)'].append(bn)
            else: rows['BSD-Q restart_backoff_base value +1 / ->None'].append(bn)
        elif f == 'restart_backoff_max':
            if newv in ('',')'): rows['BSD-R restart_backoff_max kwarg deleted (default 300.0 wins)'].append(bn)
            else: rows['BSD-S restart_backoff_max value +1 / ->None'].append(bn)
        else: rows['BSD-Z other :: '+old[:40]].append(bn)
    elif base == '_build_configs_from_compose':
        if old.startswith('logger.warning'): rows['C1 logger.warning message -> None (fallback path)'].append(bn)
        elif 'build_service_configs(' in old:
            if 'None)' in new or new.endswith(', )'): rows['C2 fallback call: include_monitoring -> None / dropped'].append(bn)
            else: rows['C3 parser/parse_file/settings arg swallow (crash on call)'].append(bn)
        else: rows['C3 parser/parse_file/settings arg swallow (crash on call)'].append(bn)
    elif base.endswith('__init__'):
        if 'if settings else' in old: rows['I1 include_monitoring else-branch True -> False'].append(bn)
        else: rows['I2 build_configs_from_compose call: settings -> None / include_monitoring -> None'].append(bn)
    elif 'discover_all' in base: rows['D1 discover_all logging-only (debug/info message text, extra dict tweaks/removals)'].append(bn)
    elif 'match_container_name' in base: rows['S1 match_container_name sort key=len dropped (len-order -> reverse-lex)'].append(bn)
    elif '_create_managed_service' in base:
        if old.startswith('health_cmd='): rows['M0 health_cmd=config.health_cmd -> None / kwarg dropped'].append(bn)
        elif 'untagged' in old: rows['M1 untagged-image defensive getattr(container,"id") default tweaks'].append(bn)
        elif 'getattr(image_tags, "tags"' in old: rows['M2 getattr(image_tags,"tags") default tweaks ([] -> None / dropped)'].append(bn)
        elif 'getattr(container, "image"' in old: rows['M3 getattr(container,"image") default dropped (crash path)'].append(bn)
        elif old.startswith('container_id='): rows['M4 container_id getattr default tweaks'].append(bn)
        else: rows['M9 other '+old[:40]].append(bn)
    else: rows['ZZ'+base].append(bn)

total = 0
out = []
for r, keys in sorted(rows.items()):
    inres = [k for k in keys if k in bn_res]
    ks = ['x'+b+f'__mutmut_{n}' for b,n in sorted(keys)]
    total += len(keys)
    out.append((r, len(keys), len(inres), ks[:3]))
print('sum:', total, '== 696?', total==696)
for r,c,i,ex in out:
    print(f'{c:4d}  res={i:2d}  {r:70s} {ex}')
json.dump({r: ['x'+b+f'__mutmut_{n}' for b,n in sorted(ks)] for r,ks in rows.items()}, open('/tmp/wp25/wp44-triage/rows.json','w'), indent=1)
