import json, re, collections

meta = json.load(open('/agents/agent-nemo2/workspace/mutants/backend/services/container_discovery.py.meta'))
ebk = meta['exit_code_by_key']
surv = set(k for k, v in ebk.items() if v == 0)

def k2bn(k):
    base, num = k.rsplit('__mutmut_', 1)
    return (base[len('backend.services.container_discovery.x'):], int(num))

bn_surv = set(k2bn(k) for k in surv)

diffs = json.load(open('/tmp/wp25/wp44-triage/diffs.json'))
dbn = {}
for k, c in diffs.items():
    b, n = k.rsplit('__mutmut_', 1)
    dbn[(b, int(n))] = c

residual = [('x_build_configs_from_compose', n) for n in (4, 6, 8)]
residual += [('x_build_service_configs', n) for n in (249, 284, 302, 360, 387, 414, 441, 468, 495, 521, 522, 549, 575, 602, 629, 656, 683, 710)]
residual += [('xǁContainerDiscoveryServiceǁ__init__', n) for n in (5, 8, 9)]
residual += [('xǁContainerDiscoveryServiceǁ_create_managed_service', n) for n in (6, 13, 16, 25, 28, 31, 32, 60, 63, 66)]
residual += [('xǁContainerDiscoveryServiceǁdiscover_all', n) for n in (18, 19, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 33, 34, 35)]
residual += [('xǁContainerDiscoveryServiceǁmatch_container_name', n) for n in (5, 7)]
bn_res = set((b[1:], n) for b, n in residual)
assert bn_res <= bn_surv

DELETED_RE = re.compile(r'^[ ,)]*$')

def substantive(bn):
    real = [(o, n) for o, n in dbn[bn] if 'mutants_' not in n]
    o, n = real[0]
    po = [p.strip() for p in o.split(' | ')]
    po = [p for p in po if re.match(r'^[\w"\x27]', p)]
    old = po[0] if po else o.strip()
    # deletion detection: every piece on the new side is punctuation/empty
    pn = [p.strip() for p in n.split(' | ')]
    pn = [p for p in pn if p and p not in (')', ' ),', '),', ',')]
    new = ' | '.join(pn)
    if DELETED_RE.match(new):
        new = ''
    return (old, new)

rows = collections.defaultdict(list)
for bn in sorted(bn_surv):
    base = bn[0]
    old, new = substantive(bn)
    if base == '_build_service_configs':
        if re.match(r'^"?([\w-]+)"?: ServiceConfig\($', old):
            rows['BSD-A dict key UPPER/XXwrap'].append(bn); continue
        if ' if settings else ' in old:
            if new.endswith('= None'):
                rows['BSD-B port-ternary LHS=None (crash when settings=None)'].append(bn)
            elif 'and False' in new:
                rows['BSD-C ternary cond `and False` (settings silently ignored)'].append(bn)
            elif 'or True' in new:
                rows['BSD-D ternary cond `or True` (AttributeError when settings=None)'].append(bn)
            else:
                rows['BSD-E ternary else-default +1 (wrong port when settings=None)'].append(bn)
            continue
        mf = re.match(r'^(\w+)=', old)
        f = mf.group(1) if mf else '?'
        deleted = (new == '')
        if f == 'display_name':
            rows['BSD-F display_name UPPER/lower/XXwrap/None'].append(bn)
        elif f == 'health_endpoint':
            rows['BSD-G health_endpoint UPPER/XXwrap/None/deleted'].append(bn)
        elif f == 'health_cmd':
            rows['BSD-H health_cmd case/XXwrap/None/deleted'].append(bn)
        elif f == 'port':
            rows['BSD-B2 port=var -> None'].append(bn)
        elif f == 'category':
            rows['BSD-I category -> None'].append(bn)
        elif f == 'startup_grace_period':
            v = re.search(r'=(\d+)', old).group(1)
            if deleted and v == '60':
                rows['BSD-J startup_grace=60 kwarg deleted (== dataclass default 60)'].append(bn)
            elif deleted:
                rows['BSD-K startup_grace kwarg deleted !=60 (default 60 wins)'].append(bn)
            else:
                rows['BSD-L startup_grace value +1 / ->None'].append(bn)
        elif f == 'max_failures':
            v = re.search(r'=(\d+)', old).group(1)
            if deleted and v == '5':
                rows['BSD-M max_failures=5 kwarg deleted (== dataclass default 5)'].append(bn)
            elif deleted:
                rows['BSD-N max_failures kwarg deleted !=5 (default 5 wins)'].append(bn)
            else:
                rows['BSD-O max_failures value +1 / ->None'].append(bn)
        elif f == 'restart_backoff_base':
            if deleted:
                rows['BSD-P backoff_base kwarg deleted (default 5.0 wins)'].append(bn)
            else:
                rows['BSD-Q backoff_base value +1 / ->None'].append(bn)
        elif f == 'restart_backoff_max':
            if deleted:
                rows['BSD-R backoff_max kwarg deleted (default 300.0 wins)'].append(bn)
            else:
                rows['BSD-S backoff_max value +1 / ->None'].append(bn)
        else:
            rows['BSD-Z other: ' + old[:40]].append(bn)
    elif base == '_build_configs_from_compose':
        if old.startswith('logger.warning'):
            rows['C1 fallback warning message -> None'].append(bn)
        elif 'build_service_configs(' in old:
            if 'None' in new[new.index('('):] or new.endswith(', )'):
                rows['C2 fallback call include_monitoring -> None/dropped (int flag unchanged)'].append(bn)
            else:
                rows['C3 parser/path/settings arg swallow (crash or wrong-path on call)'].append(bn)
        else:
            rows['C3 parser/path/settings arg swallow (crash or wrong-path on call)'].append(bn)
    elif base.endswith('__init__'):
        if 'if settings else' in old:
            rows['I1 include_monitoring else-branch True->False (no-settings case)'].append(bn)
        else:
            rows['I2 compose-call args: settings->None / include_monitoring->None'].append(bn)
    elif 'discover_all' in base:
        rows['D1 logging-only: debug/info message text + extra dict tweaks/removals'].append(bn)
    elif 'match_container_name' in base:
        rows['S1 sort key=len dropped -> reverse-lexicographic order'].append(bn)
    elif '_create_managed_service' in base:
        if old.startswith('health_cmd='):
            rows['M0 health_cmd -> None / kwarg dropped'].append(bn)
        elif 'untagged' in old:
            if '[:13]' in new:
                rows['M1b untagged id slice 12 -> 13'].append(bn)
            else:
                rows['M1a untagged getattr(container,id) defensive-default tweaks'].append(bn)
        elif 'getattr(image_tags' in old:
            if new == '':
                rows['M2b tags default dropped -> TypeError on None-tags object'].append(bn)
            else:
                rows['M2a tags default [] -> None (both falsy)'].append(bn)
        elif 'getattr(container, "image"' in old:
            rows['M3 image getattr default dropped (image=None treated as present)'].append(bn)
        elif old.startswith('container_id='):
            rows['M4 container_id getattr default tweaks ("" -> None/"XXXX"/dropped)'].append(bn)
        else:
            rows['M9 other: ' + old[:40]].append(bn)
    else:
        rows['ZZ ' + base].append(bn)

total = 0
out = {}
for r, keys in sorted(rows.items()):
    inres = [k for k in keys if k in bn_res]
    ks = ['x' + b + '__mutmut_' + str(n) for b, n in sorted(keys)]
    out[r] = {'count': len(keys), 'residual': len(inres), 'examples': ks[:3], 'keys': ks}
    total += len(keys)
    print(f"{len(keys):4d} res={len(inres):2d}  {r:66s} {ks[:3]}")
print('SUM', total, '==696:', total == 696)
json.dump(out, open('/tmp/wp25/wp44-triage/rows.json', 'w'), indent=1)
