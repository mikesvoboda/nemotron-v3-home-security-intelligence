import json, re, collections
lines=[l.rstrip('\n') for l in open('/tmp/wp25/wp44-triage/compact.txt')]
assert len(lines)==125, len(lines)
def cls(fn, minus, plus):
    # singleton construct
    if fn=='x_get_service_registry' and 'ServiceRegistry(' in plus: return ('J-singleton-redis-none','TEST-GAP')
    if fn=='x_get_service_registry' or fn=='x_reset_service_registry': return ('I-singleton-logtext','EQUIVALENT')
    if fn.endswith('_apply_loaded_state'):
        if 'state.get' in plus:
            if re.search(r'\", \)$', plus): return ('H1-apply-default-dropped','TEST-GAP')
            if re.search(r', None\)$', plus): return ('H1-apply-default-dropped','TEST-GAP')
            return ('H2-apply-default-wrong','TEST-GAP')
        return ('?apply-other','?')
    if fn.endswith('persist_state'):
        if 'if (service.last' in plus: return ('E-persist-timestamp-ternary','TEST-GAP')
    # logger call mutations
    islog = minus.startswith('logger.') or minus.startswith('"') or minus.startswith("'") or minus.startswith('logger')
    if re.match(r'^logger\.\w+\(extra=', plus) or (re.match(r'^logger\.\w+\($', plus)):
        return ('K-logmsg-removed-typeerror','TEST-GAP')
    # msg -> None (multi-line warning form)
    if plus.strip()=='None,': return ('A-log-msg-text','EQUIVALENT')
    if plus.strip()=='extra=None,' or plus.strip()=='extra=None)': return ('B-log-extra-payload','LOW-VALUE')
    if plus.strip()==')' and 'extra=' in minus: return ('B-log-extra-payload','LOW-VALUE')
    if 'extra=None' in plus: return ('B-log-extra-payload','LOW-VALUE')
    if re.search(r'\)$', plus) and 'extra=' in plus and 'extra=' in minus:
        # same call, extra payload changed?
        mkeys=set(re.findall(r'"([A-Za-z_]+)":', minus)); pkeys=set(re.findall(r'"([A-Za-z_]+)":', plus))
        if mkeys!=pkeys: return ('B-log-extra-payload','LOW-VALUE')
        if 'str(None)' in plus: return ('B-log-extra-payload','LOW-VALUE')
        # message text changed only
        return ('A-log-msg-text','EQUIVALENT')
    if 'extra=' in plus and 'extra=' not in minus: return ('B-log-extra-payload','LOW-VALUE')
    if re.search(r'\",$', plus) or 'logger.' in plus: return ('A-log-msg-text','EQUIVALENT')
    return ('?unclassified','?')
groups=collections.defaultdict(list)
for l in lines:
    key,minus,plus = l.split('\t')
    fn=key.rsplit('#',1)[0]; n=int(key.rsplit('#',1)[1])
    g,c=cls(fn,minus.replace('-','',1) if minus.startswith('-') else minus, plus.lstrip('+'))
    groups[(g,c)].append(key)
tot=0
for (g,c),ks in sorted(groups.items()):
    print(f'{len(ks):4d}  {c:12s} {g}')
    print('        ', ', '.join(k.rsplit("#",1)[0].split(".")[-1]+"#"+k.rsplit("#",1)[1] for k in ks[:3]))
    tot+=len(ks)
print('TOTAL', tot)
json.dump({f'{g}|{c}':ks for (g,c),ks in groups.items()}, open('/tmp/wp25/wp44-triage/groups.json','w'), indent=1)
