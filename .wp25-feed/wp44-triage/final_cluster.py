import json, collections, re

meta = json.load(open('/agents/agent-nemo2/workspace/mutants/backend/services/container_discovery.py.meta'))
ebk = meta['exit_code_by_key']
surv = set(k for k,v in ebk.items() if v==0)
def key_to_bn(k):
    base, num = k.rsplit('__mutmut_',1)
    return (base[len('backend.services.container_discovery.x'):], int(num))
bn_surv = set(key_to_bn(k) for k in surv)

diffs = json.load(open('/tmp/wp25/wp44-triage/diffs.json'))
diff_bn = {}
for k,c in diffs.items():
    base, num = k.rsplit('__mutmut_',1)
    diff_bn[(base,int(num))] = c

residual = set("""_build_configs_from_compose__mutmut_4|_build_configs_from_compose__mutmut_6|_build_configs_from_compose__mutmut_8
_build_service_configs__mutmut_249|_build_service_configs__mutmut_284|_build_service_configs__mutmut_302
_build_service_configs__mutmut_360|_build_service_configs__mutmut_387|_build_service_configs__mutmut_414
_build_service_configs__mutmut_441|_build_service_configs__mutmut_468|_build_service_configs__mutmut_495
_build_service_configs__mutmut_521|_build_service_configs__mutmut_522|_build_service_configs__mutmut_549
_build_service_configs__mutmut_575|_build_service_configs__mutmut_602|_build_service_configs__mutmut_629
_build_service_configs__mutmut_656|_build_service_configs__mutmut_683|_build_service_configs__mutmut_710""".split('|'))
# add the class-method residual keys with ǁ
for n in (5,8,9): residual.add(f'ǁContainerDiscoveryServiceǁ__init____mutmut_{n}')
for n in (6,13,16,25,28,31,32,60,63,66): residual.add(f'ǁContainerDiscoveryServiceǁ_create_managed_service__mutmut_{n}')
for n in (18,19,21,22,23,24,25,26,27,28,29,30,31,33,34,35): residual.add(f'ǁContainerDiscoveryServiceǁdiscover_all__mutmut_{n}')
for n in (5,7): residual.add(f'ǁContainerDiscoveryServiceǁmatch_container_name__mutmut_{n}')
bn_residual = set(key_to_bn('backend.services.container_discovery.x'+r) for r in residual)
print('residual mapped:', len(bn_residual), 'missing from survivors set:', len(bn_residual - bn_surv))

def field_of(old,new):
    m = re.match(r'^(\w+)=', old)
    return m.group(1) if m else None

def classify(base, old, new):
    if base == '_build_service_configs':
        f = field_of(old,new)
        if f in ('display_name',): return 'bsd-display_name string tweak (case/XX-wrap/None)'
        if f == 'health_endpoint': return 'bsd-health_endpoint string tweak'
        if f == 'category': return 'bsd-category=<enum> -> None'
        if f == 'startup_grace_period':
            if new=='' :
                return 'bsd-startup_grace_period=60 kwarg DELETED (== dataclass default)' if '60' in old else f'bsd-startup_grace_period=<>60 kwarg DELETED (default 60 wins)'
            return 'bsd-startup_grace_period value changed (+1 / ->None)'
        if f == 'max_failures':
            if new=='':
                return 'bsd-max_failures=5 kwarg DELETED (== dataclass default)' if 'max_failures=5' in old else 'bsd-max_failures=10 kwarg DELETED (default 5 wins)'
            return 'bsd-max_failures value changed (+1 / ->None)'
        if f == 'restart_backoff_base':
            return 'bsd-restart_backoff_base kwarg DELETED (default 5.0 wins)' if new=='' else 'bsd-restart_backoff_base value changed (+1 / ->None)'
        if f == 'restart_backoff_max':
            return 'bsd-restart_backoff_max kwarg DELETED (default 300.0 wins)' if new=='' else 'bsd-restart_backoff_max value changed (+1 / ->None)'
        if f is None and old.endswith('ServiceConfig('):
            return 'bsd-dict key string tweak (case/XX-wrap)'
        if old.endswith('if settings else 9093'.split(' else ')[0]+' else '+old.split('else ')[-1]) or ' if settings else ' in old:
            # port ternary family
            return 'bsd-port ternary mutations (=None / and False / or True / default+1)'
        return f'bsd-OTHER :: {old[:60]} => {new[:60]}'
    if base == '_build_configs_from_compose':
        if old.startswith('logger.warning'): return 'compose-logger.warning message -> None'
        return 'compose-arg/return-object mutation (parser, parse_file path, fallback args)'
    if base.endswith('__init__'):
        if 'if settings else' in old: return 'init-include_monitoring default-branch flip (else True->False)'
        return 'init-build_configs_from_compose arg swallow/shift (settings -> None)'
    if 'discover_all' in base: return 'discover_all-logging-only mutations (debug/info message text, extra dict)'
    if 'match_container_name' in base: return 'match_container_name-sort key dropped (key=len -> None)'
    if '_create_managed_service' in base:
        if old.startswith('health_cmd='): return 'create_managed_service-health_cmd wiring (->None / kwarg deleted)'
        if old.startswith('container_id='): return 'create_managed_service-defensive container.id getattr default tweaks'
        if 'untagged' in old: return 'create_managed_service-defensive untagged-image getattr/default/slice tweaks'
        if 'getattr(container, "image"' in old or 'getattr(image_tags, "tags"' in old: return 'create_managed_service-defensive image/tags getattr default tweaks'
        return f'cms-OTHER :: {old[:60]} => {new[:60]}'
    return f'OTHER-{base} :: {old[:50]} => {new[:50]}'

clusters = collections.defaultdict(list)
for bn in sorted(bn_surv, key=lambda x:(x[0],x[1])):
    c = diff_bn.get(bn)
    if c is None:
        clusters['NO-DIFF'].append(bn); continue
    # pick the substantive change (skip trailing mutmut-dict registration junk)
    real = [(o,n) for o,n in c if 'mutants_' not in n and '@_mutmut_mutated' not in n]
    if not real: real = c
    if len(real)>1:
        # MULTI: use first substantive
        pass
    o,n = real[0]
    # handle 'kwarg,|)' spans -> strip the ' ),'
    # simpler: if span includes closing paren only, drop it
    parts_o = [p.strip() for p in o.split(' | ')]
    parts_o = [p for p in parts_o if p not in (')',)]
    o2 = ' | '.join(parts_o)
    lbl = classify(bn[0], o2, n)
    clusters[lbl].append(bn)

total=0
lines=[]
for lbl, keys in sorted(clusters.items(), key=lambda x:-len(x[1])):
    inres = [k for k in keys if k in bn_residual]
    keys_s = ['x'+b+f'__mutmut_{n}' for b,n in sorted(keys)]
    total+=len(keys)
    lines.append(f'{len(keys)}\t{len(inres)}\t{lbl}\t{keys_s[:3]}')
print('TOTAL:', total)
print('\n'.join(lines))
