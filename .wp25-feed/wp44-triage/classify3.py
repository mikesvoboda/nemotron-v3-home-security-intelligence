import json, re, collections
lines=[l.rstrip('\n') for l in open('/tmp/wp25/wp44-triage/compact.txt')]
def cls(fn, M, P):
    if fn in ('x_get_service_registry','x_reset_service_registry'):
        return ('C3','TEST-GAP') if 'redis_client' in P.replace(' ','') and 'None' in P else ('E2','EQUIVALENT')
    if 'and False' in P: return ('C2','TEST-GAP')
    if fn.endswith('_apply_loaded_state') and 'state.get' in P: return ('C1','TEST-GAP')
    if re.match(r'^logger\.\w+\(extra=', P): return ('C6','LOW-VALUE')
    if P.strip()==')': return ('C7b','LOW-VALUE')           # extra kwarg removed entirely
    if 'extra=None' in P: return ('C7a','LOW-VALUE')          # extra=None
    if M.strip().startswith('extra=') and P.strip().startswith('extra='):
        mk=set(re.findall(r'"([A-Za-z_]+)":', M)); pk=set(re.findall(r'"([A-Za-z_]+)":', P))
        if 'str(None)' in P: return ('C8','LOW-VALUE')
        if mk!=pk: return ('C7c','LOW-VALUE')                  # payload key renamed
        return ('C7d','LOW-VALUE')
    if 'extra=' in M and 'extra=' not in P: return ('C7b','LOW-VALUE')
    return ('E1','EQUIVALENT')
NAMES={'C1':'_apply_loaded_state dict.get() default dropped or wrong on state restore',
 'C2':'persist_state timestamp ternary guard forced False -> last_*__at always null',
 'C3':'get_service_registry singleton discards the init_redis() client (persist silently dead)',
 'C6':'logger call msg arg removed -> TypeError at runtime (debug path only)',
 'C7a':'logger extra=None (drops structured service_name/error payload)',
 'C7b':'logger extra kwarg removed (drops structured payload)',
 'C7c':'logger extra payload key renamed (service_name/error/restart_count -> XX..XX / UPPER)',
 'C7d':'logger extra payload value altered',
 'C8':'logger extra error value str(e) -> str(None)',
 'E1':'logger.debug/warning message literal text changed (None / XX-wrapped / case)',
 'E2':'singleton logger.info/debug message literal text changed'}
CLS={'C1':'TEST-GAP','C2':'TEST-GAP','C3':'TEST-GAP','C6':'LOW-VALUE','C7a':'LOW-VALUE','C7b':'LOW-VALUE','C7c':'LOW-VALUE','C7d':'LOW-VALUE','C8':'LOW-VALUE','E1':'EQUIVALENT','E2':'EQUIVALENT'}
groups=collections.defaultdict(list)
for l in lines:
    key,minus,plus=l.split('\t')
    fn=key.rsplit('#',1)[0]
    g,_=cls(fn, minus[1:] if minus.startswith('-') else minus, plus[1:] if plus.startswith('+') else plus)
    groups[g].append(key)
tot=0
for g in sorted(groups, key=lambda x:(CLS[x],x)):
    ks=groups[g]; tot+=len(ks)
    print(f'{len(ks):4d} {CLS[g]:10s} {g}  {NAMES[g]}')
    print('      ', ', '.join(ks[:3]))
print('TOTAL',tot)
json.dump({g:{'count':len(v),'classification':CLS[g],'pattern':NAMES[g],'keys':v} for g,v in groups.items()},
          open('/tmp/wp25/wp44-triage/final.json','w'), indent=1)
