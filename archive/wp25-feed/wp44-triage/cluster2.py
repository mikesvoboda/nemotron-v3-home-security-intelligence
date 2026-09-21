import json, collections, re
d = json.load(open('/tmp/wp25/wp44-triage/export_service_diffs.json'))
sig = collections.defaultdict(list)
NOISE = re.compile(r'mutmut generated|^mutants_|^\s+mutants_')
for k,v in d.items():
    minus, plus = [], []
    for l in v.splitlines():
        if l.startswith('---') or l.startswith('+++') or l.startswith('@@'):
            continue
        if l.startswith('-'):
            body = l[1:].strip()
            if not NOISE.search(body): minus.append(body)
        elif l.startswith('+'):
            body = l[1:].strip()
            if not NOISE.search(body): plus.append(body)
    tail = k.split('export_service.')[1]
    fn = tail.rsplit('__mutmut_',1)[0]
    s = (fn, ' || '.join(minus), ' || '.join(plus))
    sig[s].append(k)
# print grouped by fn, unique signatures
by_fn = collections.defaultdict(list)
for s, keys in sig.items():
    by_fn[s[0]].append((s, keys))
total = 0
for fn in sorted(by_fn):
    entries = sorted(by_fn[fn], key=lambda x: -len(x[1]))
    n = sum(len(keys) for s,keys in entries)
    total += n
    print(f'{"="*90}\n### {fn}  (survivors={n}, unique diffs={len(entries)})')
    for s, keys in entries:
        print(f'  [{len(keys)}] keys={keys[:3]}')
        if s[1]: print(f'      - {s[1][:220]}')
        if s[2]: print(f'      + {s[2][:220]}')
print('TOTAL', total)
