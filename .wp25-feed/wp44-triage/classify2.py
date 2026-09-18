import json, re, collections
lines=[l.rstrip('\n') for l in open('/tmp/wp25/wp44-triage/compact.txt')]
assert len(lines)==125
def cls(fn, minus, plus):
    P=plus; M=minus
    if fn in ('x_get_service_registry','x_reset_service_registry'):
        if 'redis_client = None' in P or 'redis_client=None' in P: return ('J','TEST-GAP')
        return ('I','EQUIVALENT')
    if 'and False' in P: return ('E','TEST-GAP')
    if fn.endswith('_apply_loaded_state') and 'state.get' in P: return ('H','TEST-GAP')
    if re.match(r'^logger\.\w+\(extra=', P): return ('K','LOW-VALUE')
    if P.strip() in (')','extra=None,',) : return ('B','LOW-VALUE')
    if 'extra=None' in P: return ('B','LOW-VALUE')
    if M.strip().startswith('extra=') and P.strip().startswith('extra='): return ('B','LOW-VALUE')
    if 'extra=' in M and 'extra=' not in P: return ('B','LOW-VALUE')
    return ('A','EQUIVALENT')
groups=collections.defaultdict(list)
for l in lines:
    key,minus,plus = l.split('\t')
    fn=key.rsplit('#',1)[0]
    g,c=cls(fn, minus[1:] if minus.startswith('-') else minus, plus[1:] if plus.startswith('+') else plus)
    groups[(g,c)].append(key)
tot=0
for (g,c),ks in sorted(groups.items()):
    print(f'{len(ks):4d}  {c:10s} {g}  e.g. '+', '.join(ks[:3]))
    tot+=len(ks)
print('TOTAL',tot)
json.dump({g:ks for (g,c),ks in groups.items()}, open('/tmp/wp25/wp44-triage/groups2.json','w'), indent=1)
